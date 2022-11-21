#!/usr/bin/env python3

import random
import signal
import textwrap
from urllib.request import urlopen

import inky.inky_uc8159 as inky
import RPi.GPIO as GPIO
from inkydev import PIN_INTERRUPT, InkyDev
from mastodon import Mastodon
from PIL import Image, ImageColor, ImageDraw, ImageFont

from credentials import access_token, api_base_url, account_id

import sys
import os
# change woriking directory to script path
os.chdir(os.path.dirname(sys.argv[0]))

# configuration

# how many posts should be loaded
max_posts = 20 

# size and position of the (cropped square) thumbnail
thumb_width = 200
thumb_x = 110
thumb_y = 125

# size, position and font of the text in the speech bubble
text_x = 245
text_y = 77
text_w = 340
text_h = 110
font_name = 'Robot_Font.otf'

post_id = 0
img_id = 0

# set up buttons
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN_INTERRUPT, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Initialise Mastodon
mastodon = Mastodon(
    access_token = access_token,
    api_base_url = api_base_url
)

# Set up InkyDev first to power on the display
inkydev = InkyDev()

# Set up the Inky Display
display = inky.Inky((600, 448))


# Functions

def get_wrapped_text(text: str, font: ImageFont.ImageFont, line_length: int):
        lines = ['']
        for word in text.split():
            line = f'{lines[-1]} {word}'.strip()
            if font.getlength(line) <= line_length:
                lines[-1] = line
            else:
                lines.append(word)
        return '\n'.join(lines)

# find the maximum font size for text to be rendered within the specified rectangle
def find_font_size(the_text, the_font, the_canvas, textbox_width, textbox_height):
    for size in range(20, 1, -1): # we start with font size 20 and make it smaller until it fits
        fo = the_font.font_variant(size=size)      
        wrapped_text = get_wrapped_text(the_text,fo,textbox_width)
        left, top , right ,bottom = the_canvas.multiline_textbbox((0,0), wrapped_text, align='center', font = fo)
        text_height = bottom - top
        if text_height < textbox_height:
            break
    return [size, wrapped_text]

# These Pillow image cropping helper function are from
# https://note.nkmk.me/python-pillow-square-circle-thumbnail/
def crop_center(pil_img, crop_width, crop_height):
    img_width, img_height = pil_img.size
    return pil_img.crop(((img_width - crop_width) // 2,
                         (img_height - crop_height) // 2,
                         (img_width + crop_width) // 2,
                         (img_height + crop_height) // 2))
# crop a square as big as possible
def crop_max_square(pil_img):
    return crop_center(pil_img, min(pil_img.size), min(pil_img.size))

# helper for gradient background by weihanglo https://gist.github.com/weihanglo/1e754ec47fdd683a42fdf6a272904535
def interpolate(f_co, t_co, interval):
    det_co =[(t - f) / interval for f , t in zip(f_co, t_co)]
    for i in range(interval):
        yield [round(f + det * i) for f, det in zip(f_co, det_co)]    

# load the post's image, create a composite image and display it 
def show_image(img, caption = '', media_id=''):

    # load the image, crop it into a square and create a thumb_width * thumb_width pixel thumbnail
    # (given the shape of the TV I'm using now this should probably be less square and more landscape) 
    image = Image.open(img)
    im_thumb = crop_max_square(image).resize((thumb_width, thumb_width),  Image.Resampling.LANCZOS)
    
    # load the background as the bottom layer
    newImage = Image.new("RGB", (600, 448))
    rectangle = ImageDraw.Draw(newImage)

    # create a gradient based on two random colours
    f_co = ImageColor.getrgb("hsl(" + str(random.randint(0,360)) + ", 100%, 50%)")
    t_co = ImageColor.getrgb("hsl(" + str(random.randint(0,360)) + ", 100%, 50%)") 
    for i, color in enumerate(interpolate(f_co, t_co, 600 * 2)):
        rectangle.line([(i, 0), (0, i)], tuple(color), width=1)
    
    # now add the thumbnail as the next layer
    newImage.paste(im_thumb, (thumb_x, thumb_y))    

    # load the projector / avatar / speech bubble layer
    foreground = Image.open("img/axprojector4.png")
    newImage.paste(foreground, (0, 0),foreground)


    # draw the assembled image 
    draw = ImageDraw.Draw(newImage)

    # load the font and find the largest possible font size for the caption to stay within the speech bubble
    font = ImageFont.FreeTypeFont(font_name)   
    font_size, wrapped_text = find_font_size(caption, font, draw, text_w, text_h)
    font = ImageFont.FreeTypeFont(font_name, font_size)

    #render the text inside the speech bubble
    draw.multiline_text((text_x, text_y), wrapped_text, font=font, fill=(0, 0, 0), align="center", anchor="mm")

    # send the image to the E Ink display
    display.set_image(newImage)
    display.show()

# grab the Mastodon post's image URL, ALT image description and author name then pass them to the show_image() function 
def show_post_image (post_id = 0, media_id = 0):
    media_url = latest_media_post[post_id].media_attachments[media_id].preview_url
    media_author = latest_media_post[post_id].account.display_name # or username
    caption = latest_media_post[post_id].media_attachments[media_id].description

    # someone forgot to add their ALT text - let's give them a gentle nudge.
    if not caption:
        caption = "Here could be a beautiful ALT description. Maybe next time?"

    media_desc =  caption + "   wrote " + str(media_author)
    try:
        the_image = urlopen(media_url)
        show_image(the_image, media_desc, media_id)
    except:
        the_image = 'img/404slide.png'
        show_image(the_image, media_desc, media_id)
    

# handle button presses
def handle_interrupt(pin):
    global post_id, img_id, max_post_id
    button_a, button_b, button_c, button_d, changed = inkydev.read_buttons()

    if changed:
        # light up buttons on press
        inkydev.set_led(0, 10 * button_a, 0, 0)
        inkydev.set_led(1, 0, 10 * button_b, 0)
        inkydev.set_led(2, 0, 0, 10 * button_c)
        inkydev.set_led(3, 10 * button_d, 0, 10 * button_d)        
        inkydev.update()
        # only continue if a button is pressed
        if not button_a and not button_b and not button_c and not button_d:
            return

        # buttons a and b decrease / increase post id
        # buttons c and d decrease / increase media_id within that post
        if(button_a):
            post_id -= 1
            img_id = 0
        elif(button_b):
                post_id += 1
                img_id = 0
        elif(button_c):
            if img_id > 0:
                img_id -= 1
        elif(button_d):
            img_id += 1

        # is the img_id within limits?
        if img_id < 0 :
            post_id -= 1
            if post_id <0 :
                post_id = 0
            img_id = len(latest_media_post[post_id].media_attachments) - 1
        elif img_id >= len(latest_media_post[post_id].media_attachments):
            img_id = 0
            post_id += 1

        # is the post_id within limits?
        if post_id < 0 :
            post_id = max_posts -1
        if post_id >= max_posts:
            post_id = 0
            
        show_post_image(post_id,img_id)
GPIO.add_event_detect(PIN_INTERRUPT, GPIO.FALLING, callback=handle_interrupt)



latest_media_post = mastodon.account_statuses(id = account_id, limit = max_posts, only_media = True) # axwax
#latest_media_post = mastodon.timeline_public(only_media=True, limit=20) # public timeline
show_post_image(post_id,0)

signal.pause()