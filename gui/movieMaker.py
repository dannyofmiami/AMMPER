"""
AMMPER Movie Maker
@Daniel Palacios

edited by Madeline Marous
"""

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import ammper_paths as P  # noqa: E402  (resolves data/ and results/ paths)

import os
import moviepy.video.io.ImageSequenceClip
from moviepy.editor import *
def movie_maker(image_folder, p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11, p12, p13, p14, p15):
    # fps=1
    #
    # image_files = [os.path.join(image_folder,img)
    #                for img in os.listdir(image_folder)
    #                if img.endswith(".png")]
    # clip = moviepy.video.io.ImageSequenceClip.ImageSequenceClip(image_files, fps=fps)
    # clip.write_videofile(image_folder + 'video.mp4')

    img = [p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11, p12, p13, p14, p15]
    img = [os.path.join(image_folder, i) for i in img]
    clips = [ImageClip(m).set_duration(1)
             for m in img]

    concat_clip = concatenate_videoclips(clips, method="compose")
    concat_clip.write_videofile(_os.path.join(P.ROOT, "visualization.mp4"), fps=24)
    return

