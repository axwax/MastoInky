#!/usr/bin/env python3

import random
import signal
import textwrap
from urllib.request import urlopen

import inky.inky_uc8159 as inky
import RPi.GPIO as GPIO
from inkydev import PIN_INTERRUPT, InkyDev
from mastodon import Mastodon
from PIL import Image, ImageDraw, ImageFont

from credentials import access_token, api_base_url, account_id

# configuration
post_id = 0
img_id = 0
max_posts = 10

thumb_width = 137
thumb_x = 107
thumb_y = 268

font_name = 'Robot_Font.otf'


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

# load the post's image, create a composite image and display it 
def show_image(img, caption = '', media_id=''):

    # load the image, crop it into a square and create a thumb_width * thumb_width pixel thumbnail
    # (given the shape of the TV I'm using now this should probably be less square and more landscape) 
    image = Image.open(img)
    im_thumb = crop_max_square(image).resize((thumb_width, thumb_width),  Image.Resampling.LANCZOS)
    
    # load the background as the bottom layer
    newImage = Image.open("img/axbg" + str(random.randint(0,3)) + ".jpg")

    # now add the thumbnail as the next layer
    newImage.paste(im_thumb, (thumb_x, thumb_y))

    # load the transparent TV image and set it as the top layer
    tv = Image.open("img/tv.png")
    newImage.paste(tv, (0, 0),tv)

    # draw the assembled image 
    draw = ImageDraw.Draw(newImage)

    # someone forgot to add their ALT text - let's give them a gentle nudge.
    if not caption:
        caption = "Here could be a beautiful ALT description. Maybe next time?"

    # load the font and find the largest possible font size for the caption to stay within the speech bubble
    font = ImageFont.FreeTypeFont(font_name)   
    font_size, wrapped_text = find_font_size(caption, font, draw, 340,110)
    font = ImageFont.FreeTypeFont(font_name, font_size)

    #render the text inside the speech bubble
    draw.multiline_text((185, 77), wrapped_text, font=font, fill=(0, 0, 0), align="center", anchor="mm")

    # send the image to the E Ink display
    display.set_image(newImage)
    display.show()

# grab the Mastodon post's image URL and ALT image description then pass them to the show_image() function 
def show_post_image (post_id = 0, media_id = 0):
    media_url = latest_media_post[post_id].media_attachments[media_id].preview_url
    media_author = latest_media_post[post_id].account.display_name # or username
    caption = latest_media_post[post_id].media_attachments[media_id].description

    # someone forgot to add their ALT text - let's give them a gentle nudge.
    if not caption:
        caption = "Here could be a beautiful ALT description. Maybe next time?"

    media_desc =  caption + "   wrote " + str(media_author)

    show_image(urlopen(media_url), media_desc, media_id)

def handle_interrupt(pin):
    global post_id, img_id, max_post_id
    button_a, button_b, button_c, button_d, changed = inkydev.read_buttons()

    if changed:
        print(f"Buttons - A: {button_a} B: {button_b} C: {button_c} D: {button_d}")
        inkydev.set_led(0, 10 * button_a, 0, 0)
        inkydev.set_led(1, 0, 10 * button_b, 0)
        inkydev.set_led(2, 0, 0, 10 * button_c)
        inkydev.set_led(3, 10 * button_d, 0, 10 * button_d)
        inkydev.update()
        if(button_a):
            if post_id > 0:
                post_id -= 1
                img_id = 0
                show_post_image(post_id,img_id)
        elif(button_b):
            if post_id < max_posts - 1:
                post_id += 1
                img_id = 0
                show_post_image(post_id,img_id)
        elif(button_c):
            if img_id > 0:
                img_id -= 1
                show_post_image(post_id,img_id)
        elif(button_d):
            if img_id < len(latest_media_post[post_id].media_attachments) - 1:
                img_id += 1
            elif post_id < max_posts - 1:
                post_id += 1
                img_id = 0
            else:
                post_id = 0
                img_id = 0
            show_post_image(post_id,img_id)               
        print(post_id, img_id)
GPIO.add_event_detect(PIN_INTERRUPT, GPIO.FALLING, callback=handle_interrupt)



latest_media_post = mastodon.account_statuses(id = account_id, limit = max_posts, only_media = True) # axwax
#latest_media_post = mastodon.timeline_public(only_media=True, limit=20) # public timeline
show_post_image(post_id,0)

signal.pause()