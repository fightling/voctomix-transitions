#!/usr/bin/env python3
from configparser import SafeConfigParser
from transitions import Composites, Transitions, L, T, R, B
from PIL import Image, ImageDraw, ImageFont
# for integer maximum size
import sys
# for calling convert to generate animated GIF
from subprocess import call
import copy
import logging
import argparse


def read_arguments():
    global Args
    # read arguments
    __all__ = ['Args']
    parser = argparse.ArgumentParser(
        description='transition - tool to generate voctomix transition animations for testing')
    parser.add_argument('composite', nargs='*',
                        help="list of composites to generate transitions between (use all available if not given)")
    parser.add_argument('-l', '--list', action='count',
                        help="list available composites")
    parser.add_argument('-g', '--generate', action='count',
                        help="generate animation")
    parser.add_argument('-t', '--title', action='count', default=0,
                        help="draw composite names and frame count")
    parser.add_argument('-k', '--keys', action='count', default=0,
                        help="draw key frames")
    parser.add_argument('-c', '--corners', action='count', default=0,
                        help="draw calculated interpolation corners")
    parser.add_argument('-C', '--cross', action='count', default=0,
                        help="draw image cross through center")
    parser.add_argument('-r', '--crop', action='count', default=0,
                        help="draw image cropping border")
    parser.add_argument('-n', '--number', action='count',
                        help="when using -g: use consecutively numbers as file names")
    parser.add_argument('-P', '--nopng', action='count',
                        help="when using -g: do not write PNG files (forces -G)")
    parser.add_argument('-L', '--leave', action='count',
                        help="when using -g: do not delete temporary PNG files")
    parser.add_argument('-G', '--nogif', action='count',
                        help="when using -g: do not generate animated GIFS")
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help="also print WARNING (-v), INFO (-vv) and DEBUG (-vvv) messages")
    Args = parser.parse_args()


def init_log():
    global Args, log
    # set up logging
    FORMAT = '%(message)s'
    logging.basicConfig(format=FORMAT)
    logging.root.setLevel([logging.ERROR, logging.WARNING,
                           logging.INFO, logging.DEBUG][Args.verbose])
    log = logging.getLogger('Transitions Test')
    if Args.nopng:
        Args.nogif = 1


def read_config(filename):
    global log, Args
    # load INI files
    config = SafeConfigParser()
    config.read(filename)
    # read frame size
    size = config.get('output', 'size').split('x')
    size = [int(size[0]), int(size[1])]
    # read frames per second
    fps = int(config.get('output', 'fps'))
    # read composites from configuration
    log.info("reading composites from configuration...")
    composites = Composites.configure(config.items('composites'), size)
    log.debug("read %d composites:\n\t%s\t" %
              (len(composites), '\n\t'.join(composites)))
    # read transitions from configuration
    log.info("reading transitions from configuration...")
    transitions = Transitions.configure(
        config.items('transitions'), composites, fps)
    log.debug("read %d transition(s):\n\t%s\t" %
              (len(transitions), '\n\t'.join(transitions)))
    # list of all relevant composites we like to target
    targets = []
    intermediates = []
    for c_name, c in composites.items():
        if c.inter:
            intermediates.append(c_name)
        else:
            targets.append(c_name)
    # maybe overwirte targets by arguments
    if Args.composite:
        # check for composites in arguments
        targets = Args.composite

        # get all possible transitions between composites
    log.debug("using %d target composite(s):\n\t%s\t" %
              (len(targets), '\n\t'.join(targets)))
    # list targets and itermediates
    if Args.list:
        print("%d targetable composite(s):\n\t%s\t" %
              (len(targets), '\n\t'.join(sorted(targets))))
        print("%d intermediate composite(s):\n\t%s\t" %
              (len(intermediates), '\n\t'.join(sorted(intermediates))))
    # return config
    return size, fps, targets, transitions, composites


def draw_transition(size, transition, name=None):
    # indices of size and tsize
    X, Y = 0, 1
    # get a font
    font = ImageFont.truetype("Arial.ttf", 20)
    # get where to flip sources
    flip_at = transition.flip()
    # animation as a list of images
    images = []
    # render all frames
    for i in range(transition.frames()):
        # create an image to draw into
        imageBg = Image.new('RGBA', size, (40, 40, 40, 255))
        imageA = Image.new('RGBA', size, (0, 0, 0, 0))
        imageB = Image.new('RGBA', size, (0, 0, 0, 0))
        imageDesc = Image.new('RGBA', size, (0, 0, 0, 0))
        imageFg = Image.new('RGBA', size, (0, 0, 0, 0))
        # create a drawing context
        drawBg = ImageDraw.Draw(imageBg)
        drawA = ImageDraw.Draw(imageA)
        drawB = ImageDraw.Draw(imageB)
        drawDesc = ImageDraw.Draw(imageDesc)
        drawFg = ImageDraw.Draw(imageFg)
        if Args.cross:
            # mark center lines
            drawFg.line((size[X] / 2, 0, size[X] / 2, size[Y]),
                        fill=(0, 0, 0, 128))
            drawFg.line((0, size[Y] / 2, size[X], size[Y] / 2),
                        fill=(0, 0, 0, 128))
        # simulate swapping sources
        a, b = transition.A(i), transition.B(i)
        if i >= flip_at:
            a, b = b, a
            if Args.title:
                text = "(swapped sources)"
                # measure text size
                tsize = drawFg.textsize(text, font=font)
                # draw info text
                drawFg.text([(size[X] - tsize[X]) / 2, size[Y] - tsize[Y] * 2],
                            text, font=font)
        if Args.crop:
            # draw source frame
            drawA.rectangle(a.rect, outline=(128, 0, 0, a.alpha))
            drawB.rectangle(b.rect, outline=(0, 0, 128, b.alpha))
        # draw cropped source frame
        drawA.rectangle(a.cropped(), fill=(128, 0, 0, a.alpha))
        drawB.rectangle(b.cropped(), fill=(0, 0, 128, b.alpha))

        acolor = (256, 128, 128, 128)
        bcolor = (128, 128, 256, 128)

        if Args.keys:
            n = 0
            for key in transition.keys():
                ac = key.A().rect
                bc = key.B().rect
                drawDesc.rectangle(ac, outline=acolor)
                text = "A.%d" % n
                drawDesc.text([ac[L] + 2,
                               ac[T] + 2],
                              text, font=font, fill=acolor)
                drawDesc.rectangle(bc, outline=bcolor)
                text = "B.%d" % n
                # measure text size
                textsize = drawDesc.textsize(text, font=font)
                drawDesc.text([bc[R] - textsize[X] - 2,
                               bc[B] - textsize[Y] - 2],
                              text, font=font, fill=bcolor)
                n += 1

        if Args.corners:
            # draw calculated corner points
            for n in range(0, i + 1):
                ar = transition.A(n).rect
                br = transition.B(n).rect
                drawDesc.rectangle(
                    (ar[R] - 2, ar[T] - 2, ar[R] + 2, ar[T] + 2), fill=acolor)
                drawDesc.rectangle(
                    (br[L] - 2, br[T] - 2, br[L] + 2, br[T] + 2), fill=bcolor)

        if Args.title:
            if not name is None:
                text = "%s - Frame %d" % (name, i)
                # measure text size
                textsize = drawFg.textsize(text, font=font)
                # draw info text
                drawFg.text([(size[X] - textsize[X]) / 2,
                             size[Y] - textsize[Y] * 4],
                            text, font=font)
        # silly way to draw on RGBA frame buffer, hey - it's python
        images.append(
            Image.alpha_composite(
                Image.alpha_composite(
                    Image.alpha_composite(
                        Image.alpha_composite(imageBg, imageA), imageB), imageDesc), imageFg)
        )
    # return resulting animation images
    return images


def save_transition_gif(filename, size, name, animation, time):
    frames = animation.frames()
    # save animation
    log.info("generating transition '%s' (%d ms, %d frames)..." %
             (name, int(time), frames))
    images = draw_transition(size, animation, name)
    if not Args.nopng:
        imagenames = []
        delay = int(time / 10.0 / frames)
        log.info("saving animation frames into temporary files '%s0000.png'..'%s%04d.png'..." %
                 (filename, filename, animation.frames() - 1))
        for i in range(0, len(images)):
            imagenames.append("%s%04d.png" % (filename, i))
            # save an image
            images[i].save(imagenames[-1])
        # generate animated GIF by calling system command 'convert'
        if not Args.nogif:
            log.info("creating animated file '%s.gif' with delay %d..." %
                     (filename, delay))
            call(["convert", "-loop", "0"] +
                 ["-delay", "100"] + imagenames[:1] +
                 ["-delay", "%d" % delay] + imagenames[1:-1] +
                 ["-delay", "100"] + imagenames[-1:] +
                 ["%s.gif" % filename])
        # delete temporary files?
        if not Args.leave:
            log.info("deleting temporary PNG files...")
            call(["rm"] + imagenames)


def render_sequence(size, fps, targets, transitions, composites):
    global log
    # generate sequence of targets
    sequence = Transitions.travel(targets)
    log.debug("generated sequence (%d items):\n\t%s\t" %
              (len(sequence), '\n\t'.join(sequence)))
    # begin at first transition
    prev_name = sequence[0]
    prev = composites[prev_name]
    # cound findings
    not_found = 0
    found = []
    # process sequence through all possible transitions
    for c_name in sequence[1:]:
        # fetch prev comüosite
        c = composites[c_name]
        # get the right transtion between prev and c
        log.info("\nrequest transition: %s -> %s" % (prev_name, c_name))
        # actually search for a transitions that does a fade between prev and c
        t_name, t = Transitions.find(prev, c, transitions)
        # count findings
        if not t_name:
            # report fetched transition
            log.warning("no transition found for: %s -> %s" %
                        (prev_name, c_name))
            not_found += 1
        else:
            # report fetched transition
            log.info("transition found: %s -> %s -> %s" %
                     (prev_name, t_name, c_name))
            log.debug(t)
            found.append(t_name)
        # if transition was found
        if t:
            # get sequence frames
            frames = t.frames()
            if Args.generate:
                name = "%s-%s" % (prev_name, c_name)
                filename = "%s" % len(found) if Args.number else name
                print("saving transition animation file '%s.gif' (%s, %d frames)..." %
                      (filename, t_name, frames))
                # generate test images for transtion and save into animated GIF
                save_transition_gif(filename, size, name,
                                    t, frames / fps * 1000.0)
        # remember current transition as next previous
        prev_name, prev = c_name, c
    # report findings
    if found:
        if Args.list:
            print("%d transition(s) available:\n\t%s" %
                  (len(found), '\n\t'.join(sorted(found))))
    if not_found:
        log.warning("%d transition(s) could NOT be found!" % not_found)


read_arguments()
init_log()
render_sequence(*read_config("composite.ini"))
