#
#  BSD 2-Clause License
#
#  Copyright (c) 2023, Felix Brendel
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


from pathlib import Path
from PIL import Image
import sys
import os

def lst_or_tpl(obj):
    return type(obj) is list or type(obj) is tuple

def param_list_to_dict(l):
    return {k:v for k,v in l}

def lerp(a, t, b):
    return (1-t)* a + t * b

def unlerp(a, x, b):
    return (x - a) / (b - a)

def remap(a, x, b, c, d):
    return lerp(c, unlerp(a,x,b), d)

def flatten(ls):
    return (item for sublist in ls for item in sublist)

import skimage
import skimage.io
import skimage.metrics

def get_similarity_values(ref, img):
    sk_ref     = skimage.io.imread(ref)
    sk_img     = skimage.io.imread(img)
    mse        = skimage.metrics.mean_squared_error(sk_ref, sk_img)
    psnr       = skimage.metrics.peak_signal_noise_ratio(sk_ref, sk_img)
    ssim       = skimage.metrics.structural_similarity(sk_ref, sk_img, channel_axis=2)

    return mse, psnr, ssim

flipped_images = 0
def create_flip_image(ref, img):
    global flipped_images

    flipped_images += 1
    base_path = ".flip/"
    Path(base_path).mkdir(parents=True, exist_ok=True)

    flip_exe = str(Path("./flip/python/flip.py").resolve())
    run_cmd = " ".join(["python ", flip_exe,
                        "-r", ref,
                        "-t", img,
                        "-d", str(Path(base_path).resolve()),
                        "-b", str(flipped_images)])
    print()
    print("Flip nr", flipped_images)
    print(run_cmd, flush=True)
    os.system(run_cmd)

    return str(Path(base_path + str(flipped_images)+".png").resolve())

cropped_image_counter = 0
def create_cropped_image(path, trim):
    global cropped_image_counter
    print("cropping ", path, "...", sep="", flush=True)

    image = Image.open(path)
    res = image.size

    # PIL crop((left, top, right, bottom))
    # latex crop: left, bottom, right, top
    image = image.crop((res[0]*trim[0], res[1]*trim[3], res[0] - res[0]*trim[2], res[1] - res[1]*trim[1]))

    cropped_image_counter += 1
    base_path = ".cropped/"
    Path(base_path).mkdir(parents=True, exist_ok=True)

    new_path = base_path + str(cropped_image_counter) + ".png"
    image.save(new_path, "png")

    return new_path

def make_image(path, out_list, width=1, trim=(0,0,0,0), trim_at_compile=True):
    if trim != (0,0,0,0) and trim_at_compile:
        path = create_cropped_image(path, trim)
        trim = (0,0,0,0)

    out_list.extend((r"""\adjincludegraphics[width=""", width,
                     r"""\linewidth,trim={{""",
                     trim[0],"\width} {",trim[1],"\height} {",trim[2],"\width} {",trim[3],"\height}",
                     """}, clip]{""",path,r"""}"""))

def make_bordered_square(path, box_px, color, out_list):
    out_list.append(r"""            \begin{tikzpicture}
              \node[anchor=south west,inner sep=0] at (0,0) {""")

    make_image(path, out_list, width=1, trim=box_px)
    out_list.extend((r"""};
                \draw[""",color,r""",ultra thick] (0,0) rectangle (\linewidth, \linewidth);
            \end{tikzpicture} \vspace{0.01\textwidth}"""))

def calc_box_dim(box, aspect):
    box_dim = [0,0,0,0]
    box_dim[0] = box[0]/10
    box_dim[1] = box[1]/10
    box_dim[2] = (10 - box[0] - box[2])/10
    box_dim[3] = (10 - box[1] - box[2]*aspect)/10

    return box_dim


def do_one_line(images, paths, headers, box1, box2, ref_width, margin, show_grid, ref_crop, out_list):
    r = Image.open(paths[0])
    res = r.size
    aspect = res[0] / res[1]

    box_1_width = calc_box_dim(box1, aspect)
    box_2_width = calc_box_dim(box2, aspect)


    # NOTE(Felix): update box if doing ref-crop
    if ref_crop != [0,0,0,0]:
        new_left  = ref_crop[0]
        new_right = 10 - ref_crop[2]

        new_bottom = ref_crop[1]
        new_top   = 10 - ref_crop[3]

        aspect = (res[0]*(10 - ref_crop[2] - ref_crop[0])) / (res[1]*(10 - ref_crop[3] - ref_crop[1]))

        box1 = [
            remap(new_left,   box1[0], new_right, 0, 10),
            remap(new_bottom, box1[1], new_top, 0, 10),
            10 / (new_right - new_left) * box1[2]
        ]

        box2 = [
            remap(new_left,   box2[0], new_right, 0, 10),
            remap(new_bottom, box2[1], new_top, 0, 10),
            10 / (new_right - new_left) * box2[2]
        ]

        # NOTE(Felix): convert grid space crop to percent\width crop
        ref_crop = [
            ref_crop[0]/10,
            ref_crop[1]/10,
            ref_crop[2]/10,
            ref_crop[3]/10,
        ]

    if ref_width == -1:
        # ref_width = 2 * (minipage_width + margin) * aspect
        ref_width = (len(images)*aspect * ((2-4*(len(images))*margin)/(len(images)) + 2*margin)) / (len(images) + 2*aspect)

    minipage_width = (1 - ref_width - (len(images)+1)*2*margin) / len(images)


    out_list.extend((r"""\begin{center}
        \bgroup
        \def\arraystretch{0.9}
        {\setlength{\tabcolsep}{""", margin, r"""\textwidth}
        \begin{tabular}{""", "c"*(len(images)+1),"""}
    """, "      & ", " & ".join(headers), r"\\"))

    # reference
    out_list.extend((r"""
        \begin{minipage}{""", ref_width, r"""\textwidth}
            \begin{tikzpicture}
              \node[anchor=south west,inner sep=0] (image)  at (0,0) {\adjincludegraphics[width=\linewidth,trim={{""", ref_crop[0],"\width} {", ref_crop[1],"\height} {", ref_crop[2],"\width} {", ref_crop[3],"\height}}, clip", r"""]{""",  paths[0], r"""}};
              \begin{scope}[
                 x={($0.1*(image.south east)$)},
                 y={($0.1*(image.north west)$)}]
    """))

    if show_grid:
        out_list.append(r"     \draw[lightgray,step=1] (image.south west) grid (image.north east);")


    # boxes
    out_list.extend((r"          \draw[orange,ultra thick] (", box1[0], ",", box1[1], ") rectangle (", box1[0]+box1[2],",", box1[1]+box1[2]*aspect, ");"))
    out_list.extend((r"          \draw[blue,ultra thick]   (", box2[0], ",", box2[1], ") rectangle (", box2[0]+box2[2],",", box2[1]+box2[2]*aspect, ");"))

    out_list.append(r"""         \end{scope}
            \end{tikzpicture}
            \vspace{0.0001\textwidth}
        \end{minipage}
    """)


    for path in paths:
        out_list.extend((r"""&
        \begin{minipage}{""",minipage_width,r"""\textwidth}"""))

        make_bordered_square(path, box_1_width, "orange", out_list=out_list)
        make_bordered_square(path, box_2_width, "blue", out_list=out_list)

        out_list.extend((r""" \vspace{""", 2*margin, r"""\textwidth} \end{minipage}"""))

    out_list.append(r"""
        \end{tabular}}
        \egroup
      \end{center}
      \vspace*{-1cm}""")


def do_horizontal_iteration_columns(images, flips, box1, box2, margin, out_list):
    #images [("name", paths...), ...]
    rows = images

    r = Image.open(rows[0][1])
    res = r.size
    aspect = res[0] / res[1]

    box_1_width = calc_box_dim(box1, aspect)
    box_2_width = calc_box_dim(box2, aspect)

    num_columns = (len(flips[0])*2)

    minipage_width = (0.9 - (num_columns*margin)) / (num_columns)

    out_list.extend((r"""\begin{center}
        \bgroup
        \def\arraystretch{0.9}
        {\setlength{\tabcolsep}{""", margin, r"""\textwidth}
        \begin{tabular}{""", "c"*(num_columns+1),"""}
    """))

    for i in range(0, num_columns//2):
        out_list.extend((r"& \multicolumn{2}{c}{iter ", i+1, r"} "))
    out_list.append(r"\\")

    for row_idx, row in enumerate(images):
        out_list.extend((r"\rotatebox[origin=c]{90}{", row[0] ,r"}"))
        squares = flatten(zip(row[1:], flips[row_idx]))
        print("suqares: ", list(flatten(zip(row[1:], flips))), flush=True)
        for square in squares:
            out_list.extend((r"""&
        \begin{minipage}{""",minipage_width,r"""\textwidth}"""))

            make_bordered_square(square, box_1_width, "orange", out_list)
            make_bordered_square(square, box_2_width, "blue", out_list)


            out_list.append(r""" \end{minipage}""")

        out_list.append(r"""\\""")

    out_list.append(r"""
        \end{tabular}}
        \egroup
      \end{center}
      \vspace*{-1cm}""")

def do_columns(paths, metrics, headers, box1, box2, margin, out_list):
    r = Image.open(paths[0][0])
    res = r.size
    aspect = res[0] / res[1]

    box_1_width = calc_box_dim(box1, aspect)
    box_2_width = calc_box_dim(box2, aspect)

    print("..................................")
    print(box1, box2)
    print(box_1_width, box_2_width)

    minipage_width = (1 - (len(paths)*2*margin)) / len(paths)

    out_list.extend((r"""\begin{center}
        \bgroup
        \def\arraystretch{0.9}
        {\setlength{\tabcolsep}{""", margin, r"""\textwidth}
        \begin{tabular}{""", "c"*(len(paths)),"""}
    """))
    out_list.extend(("      ", " & ".join(headers), r"\\"))

    first_iter = True

    best_mse  = metrics[0][0]
    best_psnr = metrics[0][1]
    best_ssim = metrics[0][2]
    for m in metrics:
        if m[0] < best_mse:
            best_mse = m[0]
        if m[1] > best_psnr:
            best_psnr = m[1]
        if m[2] > best_ssim:
            best_ssim = m[2]

    for idx, path_pack in enumerate(paths):
        if not first_iter:
            out_list.append("&")
        first_iter = False

        out_list.extend((r"""
        \begin{minipage}{""",minipage_width,r"""\textwidth}"""))

        make_bordered_square(path_pack[0], box_1_width, "orange",out_list)
        make_bordered_square(path_pack[1], box_1_width, "orange",out_list)
        make_bordered_square(path_pack[0], box_2_width, "blue",out_list)
        make_bordered_square(path_pack[1], box_2_width, "blue",out_list)

        def maybe_make_blue(val, cond):
            val = round(val, 2)
            if cond:
                return r"\textcolor{blue}{"+str(val)+"}"
            return val

        if metrics:
            m = metrics[idx]
            out_list.extend((r"""
         \vspace{0.1cm}
         \begin{tabular}{ l l }
          MSE  &  """, maybe_make_blue(m[0], m[0] == best_mse),  r"""\\
          PSNR &  """, maybe_make_blue(m[1], m[1] == best_psnr), r"""\\
          SSIM &  """, maybe_make_blue(m[2], m[2] == best_ssim), r"""
         \end{tabular}\vspace{0.9cm}"""))
        else:
            out_list.extend((r""" \vspace{""", 2*margin, r"""\textwidth}"""))

        out_list.append(r""" \end{minipage}""")

    out_list.append(r"""
        \end{tabular}}
        \egroup
      \end{center}
      \vspace*{-1cm}""")


## ----------------------
##       figures
## ----------------------

def one_line_figure(out_list, ref="", ref_crop=(0, 0, 0, 0), ref_width=-1, margin=0.005, box1=(0, 0, 1), box2=(1, 1, 1),
                    cmp1="", cmp2="", cmp3="", cmp4="", cmp5="", show_grid=False):
    images  = [i    for i in (ref, cmp1, cmp2, cmp3, cmp4, cmp5) if i != ""]
    paths   = [p[1] if lst_or_tpl(p) else p for p in images]
    headers = [p[0] if lst_or_tpl(p) else "" for p in images]
    do_one_line(images=images, paths=paths, headers=headers,
                box1=box1, box2=box2, ref_width=ref_width,
                margin=margin, show_grid=show_grid, ref_crop=ref_crop, out_list=out_list)


def vertical_flip_figure(out_list, ref="", ref_crop=(0, 0, 0, 0), ref_width=-1, margin=0.005, box1=(0, 0, 1), box2=(1, 1, 1),
                         cmp1="", cmp2="", cmp3="", cmp4="", cmp5="", show_grid=False):
    ref_img = [ref]
    paths   = [p[1] if lst_or_tpl(p) else p for p in ref_img]
    headers = [p[0] if lst_or_tpl(p) else "" for p in ref_img]
    do_one_line(images=ref_img, paths=paths, headers=headers,
                box1=box1, box2=box2, ref_width=ref_width,
                margin=margin, show_grid=show_grid, ref_crop=ref_crop, out_list=out_list)

    images  = [i for i in (cmp1, cmp2, cmp3, cmp4, cmp5) if i != ""]

    for i in images:
        if len(i) != 2:
            raise Exception("Each comparison image needs to have 2 components: " +
                            "name, path")

    paths   = [(p[1], create_flip_image(ref[1], p[1])) for p in images]
    metrics = [get_similarity_values(ref[1], p[1]) for p in images]
    headers = [p[0] if lst_or_tpl(p) else "" for p in images]
    do_columns(paths=paths, metrics=metrics, headers=headers,
               box1=box1, box2=box2, margin=margin, out_list=out_list)


def horizontal_iterations_figure(out_list, ref="", ref_crop=(0, 0, 0, 0), ref_width=-1, margin=0.005, box1=(0, 0, 1), box2=(1, 1, 1),
                                 cmp1="", cmp2="", cmp3="", cmp4="", cmp5="", show_grid=False):
    ref_img = [ref]
    paths   = [p[1] if lst_or_tpl(p) else p for p in ref_img]
    headers = [p[0] if lst_or_tpl(p) else "" for p in ref_img]
    do_one_line(images=ref_img, paths=paths, headers=headers,
                box1=box1, box2=box2, ref_width=ref_width,
                margin=margin, show_grid=show_grid, ref_crop=ref_crop, out_list=out_list)

    images  = [i for i in (cmp1, cmp2, cmp3, cmp4, cmp5) if i != ""]
    if len(images) == 0:
        raise Exception("No comparison images supplied")

    flips = []
    for img in images:
        l = []

        for iter in img[1:]:
            l.append(create_flip_image(ref[1], iter))

        flips.append(l)

    num_images = len(images[0])-1

    for i in images:
        if len(i)-1 != num_images:
            raise Exception("All comparisons need to have the same number of images")

    do_horizontal_iteration_columns(images=images, flips=flips, box1=box1, box2=box2, margin=margin, out_list=out_list)



def make_latex_standalone(file_name, content, compile=True):
    latex_list = [r"""\documentclass[preview]{standalone}
\usepackage{tikz}
\usepackage{adjustbox}
\usetikzlibrary{calc}

\begin{document}"""]

    latex_list.extend(content)

    latex_list.append(r"""\end{document}""")

    latex_list = (str(e) for e in latex_list)

    with open(file_name, "w") as out_file:
        print("".join(latex_list), file=out_file)

    if compile:
        print("compiling:")
        res = os.system("pdflatex " + file_name)
        if res == 0:
            print("success! :)")
        else:
            print("no success :(")

        return res


if __name__ ==  "__main__":
    # # one line
    # llist = []
    # one_line_figure(ref=("4000spp", "./images/eaw_japan-4000spp.png"),
    #                 box1=(7.85, 7.5, 0.8), box2=(5.1, 7.3, 0.5),
    #                 cmp1=("1 iter", "./images/eaw_japan-4spp-1-iter-p+n.png"),
    #                 cmp2=("2 iter", "./images/eaw_japan-4spp-2-iter-p+n.png"),
    #                 out_list=llist)
    # make_latex_standalone("one_line.tex", llist);

    # # long line
    # llist = []
    # one_line_figure(box1=(7.85, 7.5, 0.8), box2=(5.1, 7.3, 0.5),
    #                 ref_crop=(4, 2, 1, 1),
    #                 ref=( "4000spp", "./images/eaw_japan-4000spp.png"),
    #                 cmp1=("1 iter",  "./images/eaw_japan-4spp-1-iter-p+n.png"),
    #                 cmp2=("2 iter",  "./images/eaw_japan-4spp-2-iter-p+n.png"),
    #                 cmp3=("3 iter",  "./images/eaw_japan-4spp-3-iter-p+n.png"),
    #                 cmp4=("4 iter",  "./images/eaw_japan-4spp-4-iter-p+n.png"),
    #                 cmp5=("5 iter",  "./images/eaw_japan-4spp-5-iter-p+n.png"),
    #                 out_list=llist)
    # make_latex_standalone("long_line.tex", llist)

    # vertical flip
    llist = []
    vertical_flip_figure(box1=(0.5, 2.5, 3.5), box2=(5.5, 2, 3),
                         ref_crop=(0, 1.5, 0, 2),
                         ref=( "4000spp", "./images/eaw_japan-4000spp.png"),
                         cmp1=("1 iter",  "./images/eaw_japan-4spp-1-iter-p+n.png"),
                         cmp2=("2 iter",  "./images/eaw_japan-4spp-2-iter-p+n.png"),
                         cmp3=("3 iter",  "./images/eaw_japan-4spp-3-iter-p+n.png"),
                         cmp4=("4 iter",  "./images/eaw_japan-4spp-4-iter-p+n.png"),
                         cmp5=("5 iter",  "./images/eaw_japan-4spp-5-iter-p+n.png"),
                         out_list=llist)
    make_latex_standalone("vertical_flip.tex", llist)

    # # # horiz iterations
    # llist = []
    # horizontal_iterations_figure(box1=(0.5, 2.5, 3.5), box2=(5.5, 2, 3),
    #                              ref_crop=(0, 1.5, 0, 2),
    #                              ref=( "4000spp", "./images/eaw_japan-4000spp.png"),
    #                              cmp1=("C+P+N",
    #                                    "./images/eaw_japan-4spp-1-iter-p+n.png",
    #                                    "./images/eaw_japan-4spp-2-iter-p+n.png",
    #                                    "./images/eaw_japan-4spp-3-iter-p+n.png",
    #                                    "./images/eaw_japan-4spp-4-iter-p+n.png",
    #                                    "./images/eaw_japan-4spp-5-iter-p+n.png"),
    #                              cmp2=("C+P",
    #                                    "./images/eaw_japan-4spp-1-iter-p.png",
    #                                    "./images/eaw_japan-4spp-2-iter-p.png",
    #                                    "./images/eaw_japan-4spp-3-iter-p.png",
    #                                    "./images/eaw_japan-4spp-4-iter-p.png",
    #                                    "./images/eaw_japan-4spp-5-iter-p.png"),
    #                              cmp3=("C+N",
    #                                    "./images/eaw_japan-4spp-1-iter-n.png",
    #                                    "./images/eaw_japan-4spp-2-iter-n.png",
    #                                    "./images/eaw_japan-4spp-3-iter-n.png",
    #                                    "./images/eaw_japan-4spp-4-iter-n.png",
    #                                    "./images/eaw_japan-4spp-5-iter-n.png"),
    #                              cmp4=("C",
    #                                    "./images/eaw_japan-4spp-1-iter.png",
    #                                    "./images/eaw_japan-4spp-2-iter.png",
    #                                    "./images/eaw_japan-4spp-3-iter.png",
    #                                    "./images/eaw_japan-4spp-4-iter.png",
    #                                    "./images/eaw_japan-4spp-5-iter.png"),
    #                              out_list=llist)
    # make_latex_standalone("horiz_iterations.tex", llist)
