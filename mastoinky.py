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

from credentials import access_token, api_base_url

# configuration
post_id = 0
img_id = 0
max_post_id = 10

# set up buttons
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN_INTERRUPT, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Initialise Mastodon
mastodon = Mastodon(
    access_token = str(access_token),
    api_base_url = str(api_base_url)
)

# Set up InkyDev first to power on the display
inkydev = InkyDev()

# Set up the Inky Display
display = inky.Inky((600, 448))


# Functions
def get_wrapped_text(text: str, font: ImageFont.ImageFont,
                     line_length: int):
        lines = ['']
        for word in text.split():
            line = f'{lines[-1]} {word}'.strip()
            if font.getlength(line) <= line_length:
                lines[-1] = line
            else:
                lines.append(word)
        return '\n'.join(lines)

def find_font_size(the_text, the_font, the_canvas, the_width, the_height):
    for size in range(20, 1, -1):
        fo = the_font.font_variant(size=size)      
        wrapped_text = get_wrapped_text(the_text,fo,the_width)
        l,t,r,b = the_canvas.multiline_textbbox((0,0), wrapped_text, align='center', font = fo)
        w = r - l
        h = b - t
        if h < the_height:
            break
    return [size, wrapped_text]

def crop_center(pil_img, crop_width, crop_height):
    img_width, img_height = pil_img.size
    return pil_img.crop(((img_width - crop_width) // 2,
                         (img_height - crop_height) // 2,
                         (img_width + crop_width) // 2,
                         (img_height + crop_height) // 2))

def crop_max_square(pil_img):
    return crop_center(pil_img, min(pil_img.size), min(pil_img.size))

def show_image(img, caption = '', media_id=''):
    image = Image.open(img)

    thumb_width = 137
    im_thumb = crop_max_square(image).resize((thumb_width, thumb_width),  Image.Resampling.LANCZOS)
    
    tv = Image.open("img/tv.png")

    newImage = Image.open("img/axbg" + str(random.randint(0,3)) + ".jpg")
    newImage.paste(im_thumb, (107,268))   
    newImage.paste(tv, (0, 0),tv)

    # someone forgot to add their ALT text - let's give them a gentle nudge.
    if not caption:
        caption = "Here could be a beautiful ALT description. Maybe next time?"

    draw = ImageDraw.Draw(newImage)
    calvin = ImageFont.FreeTypeFont('calvin.ttf')   
    font_size, wrapped_text = find_font_size(caption, calvin, draw, 340,110)
    font = ImageFont.FreeTypeFont('calvin.ttf', font_size)
    #print(font_size,wrapped_text)
    draw.multiline_text((185, 77), wrapped_text, font=font, fill=(0, 0, 0), align="center", anchor="mm")

    display.set_image(newImage)
    display.show()

def show_post_image (post_id = 0, media_id = 0):
    media_url = latest_media_post[post_id].media_attachments[media_id].preview_url
    media_desc = latest_media_post[post_id].media_attachments[media_id].description
    #print(media_url)
    #print(media_desc)
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
            if post_id < max_post_id - 1:
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
            elif post_id < max_post_id - 1:
                post_id += 1
                img_id = 0
            else:
                post_id = 0
                img_id = 0
            show_post_image(post_id,img_id)               
        print(post_id, img_id)
GPIO.add_event_detect(PIN_INTERRUPT, GPIO.FALLING, callback=handle_interrupt)




#latest_media_post = mastodon.account_statuses(id = 108194681371449586, limit = max_post_id, only_media = True)
#latest_media_post = mastodon.account_statuses(id = 198442, limit = max_post_id, only_media = True) # foosel

latest_media_post = mastodon.account_statuses(id = 108194681371449586, limit = max_post_id, only_media = True) # axwax
#latest_media_post = mastodon.account_statuses(id = 44062, limit = max_post_id, only_media = True) #aallan
#latest_media_post = mastodon.account_statuses(id = 109247742049537943, limit = max_post_id, only_media = True) #liz

#latest_media_post = mastodon.timeline_public(only_media=True, limit=20) # public timeline
#109263796514817006

#print(len(latest_media_post[post_id].media_attachments))
show_post_image(post_id,0)

signal.pause()