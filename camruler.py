# -------------------------------
# imports
# -------------------------------

# builtins
import os
import sys
import time
# import traceback
from math import expm1, hypot
from cv2 import destroyAllWindows, waitKey
from ast import operator
import tkinter as tk
from tkinter import messagebox
import mysql.connector
from tkinter import *

# must be installed using pip
# python3 -m pip install opencv-python
import numpy as np
import cv2

# local clayton libs
import frame_capture
import frame_draw

global e1
global e2

# -------------------------------
# camera
# -------------------------------
camera_id = 0
if len(sys.argv) > 1:
    camera_id = sys.argv[1]
    if camera_id.isdigit():
        camera_id = int(camera_id)

# camera thread setup
camera = frame_capture.Camera_Thread()
camera.camera_source = camera_id  # SET THE CORRECT CAMERA NUMBER
camera.camera_width, camera.camera_height = 1280, 1024
camera.camera_frame_rate = 30
camera.camera_fourcc = cv2.VideoWriter_fourcc(*"MJPG")

# start camera thread
camera.start()

# initial camera values (shortcuts for below)
width = camera.camera_width
height = camera.camera_height
area = width*height
cx = int(width/2)
cy = int(height/2)
dm = hypot(cx, cy)  # max pixel distance
frate = camera.camera_frame_rate
print('CAMERA:', [camera.camera_source, width, height, area, frate])

# -------------------------------
# frame drawing/text module
# -------------------------------

draw = frame_draw.DRAW()
draw.width = width
draw.height = height

# -------------------------------
# conversion (pixels to measure)
# -------------------------------

# distance units designator
unit_suffix = 'cm'

# calibrate every N pixels
pixel_base = 30

# maximum field of view from center to farthest edge
# should be measured in unit_suffix
mysqldb = mysql.connector.connect(host="localhost", user="root", password="", database="balitjestroGrading")
cursor = mysqldb.cursor()
cursor.execute("SELECT rullerScale FROM jarakKamera")
myresult = cursor.fetchall()
cal_range = myresult[-1][-1]

# initial calibration values table {pixels:scale}
# this is based on the frame size and the cal_range
cal = dict([(x, cal_range/dm) for x in range(0, int(dm)+1, pixel_base)])

# calibration loop values
# inside of main loop below
cal_base = 5
cal_last = None

# calibration update
def cal_update(x, y, unit_distance):

    # basics
    pixel_distance = hypot(x, y)
    scale = abs(unit_distance/pixel_distance)
    target = baseround(abs(pixel_distance), pixel_base)

    # low-high values in distance
    low = target*scale - (cal_base/2)
    high = target*scale + (cal_base/2)

    # get low start point in pixels
    start = target
    if unit_distance <= cal_base:
        start = 0
    else:
        while start*scale > low:
            start -= pixel_base

    # get high stop point in pixels
    stop = target
    if unit_distance >= baseround(cal_range, pixel_base):
        high = max(cal.keys())
    else:
        while stop*scale < high:
            stop += pixel_base

    # set scale
    for x in range(start, stop+1, pixel_base):
        cal[x] = scale
        print(f'CAL: {x} {scale}')


# read local calibration data
calfile = 'camruler_cal.csv'
if os.path.isfile(calfile):
    with open(calfile) as f:
        for line in f:
            line = line.strip()
            if line and line[0] in ('d',):
                axis, pixels, scale = [_.strip() for _ in line.split(',', 2)]
                if axis == 'd':
                    print(f'LOAD: {pixels} {scale}')
                    cal[int(pixels)] = float(scale)

# convert pixels to units
def conv(x, y):

    d = distance(0, 0, x, y)

    scale = cal[baseround(d, pixel_base)]

    return x*scale, y*scale

# round to a given base
def baseround(x, base=1):
    return int(base * round(float(x)/base))

# distance formula 2D
def distance(x1, y1, x2, y2):
    return hypot(x1-x2, y1-y2)

# -------------------------------
# define frames
# -------------------------------

# define display frame
framename = "Object Measurement"
cv2.namedWindow(framename, flags=cv2.WINDOW_NORMAL | cv2.WINDOW_GUI_NORMAL)

#define gui function
def Add():
    oprName = e1.get()
    camDist = e2.get()

    mysqldb = mysql.connector.connect(
        host="localhost", user="root", database="balitjestroGrading")
    mycursor = mysqldb.cursor()

    try:
       sql = "INSERT INTO jarakKamera (operatorName,rullerScale) VALUES (%s, %s)"
       val = (oprName, camDist)
       mycursor.execute(sql, val)
       mysqldb.commit()
       messagebox.showinfo("Caution!", "Added!")
       e1.delete(0, END)
       e2.delete(0, END)
    except Exception as e:
       print(e)
       mysqldb.rollback()
       mysqldb.close()


def update():
    oprName = e1.get()
    camDist = e2.get()
    mysqldb = mysql.connector.connect(
        host="localhost", user="root", password="", database="balitjestroGrading")
    mycursor = mysqldb.cursor()

    try:
       sql = "Update jarakKamera set operatorName= %s,rullerScale= %s where id=(SELECT MAX(ID) FROM jarakKamera)"
       val = (oprName, camDist)
       mycursor.execute(sql, val)
       mysqldb.commit()
       lastid = mycursor.lastrowid
       messagebox.showinfo("", "Updated!")
       e1.delete(0, END)
       e2.delete(0, END)

    except Exception as e:

       print(e)
       mysqldb.rollback()
       mysqldb.close()


def config():
    mysqldb = mysql.connector.connect(host="localhost", user="root", password="", database="balitjestroGrading")
    mycursor = mysqldb.cursor()
    isiDatabase = "SELECT COUNT(*) FROM jarakKamera"
    mycursor.execute(isiDatabase)
    myresult = mycursor.fetchall()
    if myresult[-1][-1] == 0:
        Add()
    else:
        update()

# -------------------------------
# key events
# -------------------------------

key_last = 0
# using ASCII code for lowercase letter
key_flags = {'config': False,  # c key
             'auto': False,   # a key
             'thresh': False,  # t key
             'percent': False,  # p key
             'norms': False,  # n key
             'lock': False,   #
             'jeruk': False,    # j key
             'lemon': False,  # l key
             'rullScale' : False 
            }


def key_flags_clear():

    global key_flags

    for key in list(key_flags.keys()):
        if key not in ('config',):
            key_flags[key] = False


def key_event(key):

    global key_last
    global key_flags
    global mouse_mark
    global cal_last

    # config mode, using ASCII code for lowercase letter
    if key == 99:
        if key_flags['config']:
            key_flags['config'] = False
        else:
            key_flags['config'] = True
            cal_last, mouse_mark = 0, None

    # normilization mode
    elif key == 110:
        if key_flags['norms']:
            key_flags['norms'] = False
        else:
            key_flags['thresh'] = False
            key_flags['percent'] = False
            key_flags['lock'] = False
            key_flags['norms'] = True
            mouse_mark = None

    # auto mode
    elif key == 97:
        if key_flags['auto']:
            key_flags['auto'] = False
        else:
            key_flags['auto'] = True
            cal_last, mouse_mark = 0, None

    # auto percent
    elif key == 112 and key_flags['auto']:
        key_flags['percent'] = not key_flags['percent']
        key_flags['thresh'] = False
        key_flags['lock'] = False

    # auto threshold
    elif key == 116 and key_flags['auto']:
        key_flags['thresh'] = not key_flags['thresh']
        key_flags['percent'] = False
        key_flags['lock'] = False

    # choose jeruk
    elif key == 106 and key_flags['auto']:
        key_flags['jeruk'] = not key_flags['jeruk']
    
    # choose lemon
    elif key == 108 and key_flags['auto']:
        key_flags['lemon'] = not key_flags['lemon']

    # set ruller
    elif key == 115 and key_flags['config']:
        key_flags['rullScale'] = not key_flags['rullScale']

    # log
    print('key:', [key, chr(key)])
    key_last = key

# -------------------------------
# mouse events
# -------------------------------

# mouse events
mouse_raw = (0, 0)  # pixels from top left
mouse_now = (0, 0)  # pixels from center
mouse_mark = None  # last click (from center)

# auto measure mouse events
auto_percent = 0.2
auto_threshold = 127
auto_blur = 5

# normalization mouse events
norm_alpha = 0
norm_beta = 255

def mouse_event(event, x, y, flags, parameters):
    # globals
    global mouse_raw
    global mouse_now
    global mouse_mark
    global key_last
    global auto_percent
    global auto_threshold
    global auto_blur
    global norm_alpha
    global norm_beta

    # update percent
    if key_flags['percent']:
        auto_percent = 5*(x/width)*(y/height)

    # update threshold
    elif key_flags['thresh']:
        auto_threshold = int(255*x/width)
        auto_blur = int(20*y/height) | 1  # insure it is odd and at least 1

    # update normalization
    elif key_flags['norms']:
        norm_alpha = int(64*x/width)
        norm_beta = min(255, int(128+(128*y/height)))

    # update mouse location
    mouse_raw = (x, y)

    # offset from center
    # invert y to standard quadrants
    ox = x - cx
    oy = (y-cy)*-1

    # update mouse location
    mouse_raw = (x, y)
    if not key_flags['lock']:
        mouse_now = (ox, oy)

    # left click event
    if event == 1:

        if key_flags['config']:
            key_flags['lock'] = False
            mouse_mark = (ox, oy)

        elif key_flags['auto']:
            key_flags['lock'] = False
            mouse_mark = (ox, oy)

        if key_flags['percent']:
            key_flags['percent'] = False
            mouse_mark = (ox, oy)

        elif key_flags['thresh']:
            key_flags['thresh'] = False
            mouse_mark = (ox, oy)

        elif key_flags['norms']:
            key_flags['norms'] = False
            mouse_mark = (ox, oy)

        elif key_flags['jeruk']:
            key_flags['jeruk'] = False
            key_flags['auto'] = False
            mouse_mark = (ox, oy)

        elif key_flags['lemon']:
            key_flags['lemon'] = False
            key_flags['auto'] = False
            mouse_mark = (ox, oy)

        elif key_flags['rullScale']:
            key_flags['rullScale'] = False
            key_flags['config'] = False
            mouse_mark = (ox, oy)

        elif not key_flags['lock']:
            if mouse_mark:
                key_flags['lock'] = True
            else:
                mouse_mark = (ox, oy)
        
        else:
            key_flags['lock'] = False
            mouse_now = (ox, oy)
            mouse_mark = (ox, oy)

        key_last = 0

    # right click event
    elif event == 2:
        key_flags_clear()
        mouse_mark = None
        key_last = 0

# register mouse callback
cv2.setMouseCallback(framename, mouse_event)

# -------------------------------
# main loop
# -------------------------------

# loop
while 1:
    # get frame
    frame0 = camera.next(wait=1)
    if frame0 is None:
        time.sleep(0.1)
        continue

    # normalize
    cv2.normalize(frame0, frame0, norm_alpha, norm_beta, cv2.NORM_MINMAX)

    # start top-left text block
    text = []

    # camera text
    fps = camera.current_frame_rate
    text.append(f'CAMERA: {fps}FPS')

    # -------------------------------
    # normalize mode
    # -------------------------------

    # setting the brightness
    if key_flags['norms']:

        # print
        text.append('')
        text.append(f'NORMILIZE MODE')
        text.append(f'ALPHA (min): {norm_alpha}')
        text.append(f'BETA (max): {norm_beta}')

    # -------------------------------
    # config mode
    # -------------------------------
    if key_flags['config']:
        # quadrant crosshairs
        draw.crosshairs(frame0, 5, weight=2, color='red', invert=True)

        # crosshairs aligned (rotated) to maximum distance
        draw.line(frame0, cx, cy, cx+cx, cy+cy, weight=1, color='red')
        draw.line(frame0, cx, cy, cx+cy, cy-cx, weight=1, color='red')
        draw.line(frame0, cx, cy, -cx+cx, -cy+cy, weight=1, color='red')
        draw.line(frame0, cx, cy, cx-cy, cy+cx, weight=1, color='red')

        # mouse cursor lines (parallel to aligned crosshairs)
        mx, my = mouse_raw
        draw.line(frame0, mx, my, mx+dm, my +
                  (dm*(cy/cx)), weight=1, color='green')
        draw.line(frame0, mx, my, mx-dm, my -
                  (dm*(cy/cx)), weight=1, color='green')
        draw.line(frame0, mx, my, mx+dm, my +
                  (dm*(-cx/cy)), weight=1, color='green')
        draw.line(frame0, mx, my, mx-dm, my -
                  (dm*(-cx/cy)), weight=1, color='green')

        # config text data
        text.append('')
        text.append(f'CONFIG MODE')

        # start cal
        if not cal_last:
            cal_last = cal_base
            caltext = f'CONFIG: Click on D = {cal_last}'

        # continue cal
        elif cal_last <= cal_range:
            if mouse_mark:
                cal_update(*mouse_mark, cal_last)
                cal_last += cal_base
            caltext = f'CONFIG: Click on D = {cal_last}'

        # done
        else:
            key_flags_clear()
            cal_last == None
            with open(calfile, 'w') as f:
                data = list(cal.items())
                data.sort()
                for key, value in data:
                    f.write(f'd,{key},{value}\n')
                f.close()
            caltext = f'CONFIG: Complete.'

        # add caltext
        draw.add_text(frame0, caltext, (cx)+100, (cy)+30, color='red')
        
        if (key_flags['rullScale'] == False) :
            mysqldb = mysql.connector.connect(host="localhost", user="root", password="", database="balitjestroGrading")
            cursor = mysqldb.cursor()
            cursor.execute("SELECT rullerScale FROM jarakKamera")
            myresult = cursor.fetchall()
            cal_range = myresult[-1][-1]
            text.append(f'Ruller Scale: {cal_range}')

        # clear mouse
        mouse_mark = None

        #Kalibrasi Skala Ruller
        if key_flags['rullScale']:
            key_flags['rullScale'] = False
            root = Tk()
            root.title('Ruller Scale Config')
            root.geometry("350x120")

            Label(root, text="Operator").place(x=10, y=20)
            Label(root, text="Ruller scale").place(x=10, y=50)

            e1 = Entry(root)
            e1.place(x=140, y=20)

            e2 = Entry(root)
            e2.place(x=140, y=50)

            Button(root, text="Config",command = config).place(x=140, y=80)
            Button(root, text="Quit", command=root.destroy).place(x=220, y=80)
            root.mainloop()

    # -------------------------------
    # auto mode
    # -------------------------------
    elif key_flags['auto']:

        mouse_mark = None

        # auto text data
        # tampil di sebelah kiri layar
        text.append('')
        text.append(f'AUTO MODE')
        text.append(f'MIN PERCENT: {auto_percent:.2f}')
        text.append(f'THRESHOLD: {auto_threshold}')
        text.append(f'GAUSS BLUR: {auto_blur}')

        # gray frame
        frame1 = cv2.cvtColor(frame0, cv2.COLOR_BGR2GRAY)

        # blur frame
        frame1 = cv2.GaussianBlur(frame1, (auto_blur, auto_blur), 0)

        # threshold frame n out of 255 (85 = 33%)
        frame1 = cv2.threshold(frame1, auto_threshold,
                               255, cv2.THRESH_BINARY)[1]

        # invert
        frame1 = ~frame1

        # find contours on thresholded image
        contours, nada = cv2.findContours(
            frame1, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # small crosshairs (after getting frame1)
        cv2.circle(frame0, (cx, cy), 5, (25, 25, 25), 3)

        # loop over the contours
        for c in contours:

            # contour data (from top left)
            x1, y1, w, h = cv2.boundingRect(c)
            x2, y2 = x1+w, y1+h
            x3, y3 = x1+(w/2), y1+(h/2)

            # percent area
            percent = 100*w*h/area

            # if the contour is too small, ignore it
            if percent < auto_percent:
                continue

            # if the contour is too large, ignore it
            elif percent > 60:
                continue

            # convert to center, then distance
            x1c, y1c = conv(x1-(cx), y1-(cy))
            x2c, y2c = conv(x2-(cx), y2-(cy))
            xlen = (abs(x1c-x2c))/10
            ylen = (abs(y1c-y2c))/10
            alen = 0
            carea=0
            if max(xlen, ylen) > 0 and min(xlen, ylen)/max(xlen, ylen) >= 0.95:
                alen = (xlen+ylen)/2
            # area of circle
            if xlen>ylen:
                carea = 3.14*xlen**2
            elif xlen<ylen:
                carea = 3.14*ylen**2

            # plot
            draw.rect(frame0, x1, y1, x2, y2, weight=2, color='red')
            
            #####################
            # RGB and Grading
            #####################
            hsv_frame = cv2.cvtColor(frame0, cv2.COLOR_BGR2HSV)
            height, width, _ = frame0.shape

            #print(frame0.shape)

            cx = int(width / 2)
            cy = int(height / 2)

            # Pick pixel value
            pixel_center = hsv_frame[cy, cx]
            hue_value = pixel_center[0]

            pixel_center_bgr = frame0[cy, cx]

            b, g, r = int(pixel_center_bgr[0]), int(pixel_center_bgr[1]), int(pixel_center_bgr[2])

            # computing the mean
            b_mean = np.mean(b)
            g_mean = np.mean(g)
            r_mean = np.mean(r)

            # setting upper limit & lower limit
            b_bawah = 0.74
            range_ab = 0.48

            ratio = r_mean/g_mean
            persen = ((ratio-b_bawah)*100)/range_ab
            r_ratio = round(persen, 0)

            font = cv2.FONT_HERSHEY_SIMPLEX

            # add Grading and RGB
            if key_flags['jeruk']:
                cv2.putText(frame0, f'JERUK', (500, 100),
                                cv2.FONT_HERSHEY_COMPLEX, 2, (128, 0, 0), 2)
                if (xlen >= 7.10 or ylen >= 7.10):
                    cv2.putText(frame0, f'Grade: A', (980, 100),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)
                    cv2.putText(frame0, f'R/G: {str(r_ratio)}%', (980, 150),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)

                elif ((xlen >= 6.10 or ylen >= 6.10)) & ((xlen <= 7.09 or ylen <= 7.09)):
                    cv2.putText(frame0, f'Grade: B', (980, 100),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)
                    cv2.putText(frame0, f'R/G: {str(r_ratio)}%', (980, 150),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)

                elif ((xlen >= 5.10 or ylen >= 5.10)) & ((xlen <= 6.09 or ylen <= 6.09)):
                    cv2.putText(frame0, f'Grade: C', (980, 100),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)
                    cv2.putText(frame0, f'R/G: {str(r_ratio)}%', (980, 150),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)

                elif ((xlen >= 4.10 or ylen >= 4.10)) & ((xlen <= 5.09 or ylen <= 5.09)):
                    cv2.putText(frame0, f'Grade: D', (980, 100),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)
                    cv2.putText(frame0, f'R/G: {str(r_ratio)}%', (980, 150),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)

                else:
                    cv2.putText(frame0, f'Grade: Abnormal', (980, 100),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)
                    cv2.putText(frame0, f'R/G: {str(r_ratio)}%', (980, 150),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)
                print(ratio)
            
            elif key_flags['lemon']:
                cv2.putText(frame0, f'LEMON', (500, 100),
                                cv2.FONT_HERSHEY_COMPLEX, 2, (128, 0, 0), 2)
                if (xlen > 7.10 or ylen > 7.10):
                    cv2.putText(frame0, f'Grade: Abnormal', (980, 100),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)
                    cv2.putText(frame0, f'R/G: {str(r_ratio)}%', (980, 150),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)

                elif ((xlen >= 6.10 or ylen >= 6.10)) & ((xlen <= 7.09 or ylen <= 7.09)):
                    cv2.putText(frame0, f'Grade: A', (980, 100),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)
                    cv2.putText(frame0, f'R/G: {str(r_ratio)}%', (980, 150),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)

                elif ((xlen >= 5.10 or ylen >= 5.10)) & ((xlen <= 6.09 or ylen <= 6.09)):
                    cv2.putText(frame0, f'Grade: B', (980, 100),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)
                    cv2.putText(frame0, f'R/G: {str(r_ratio)}%', (980, 150),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)

                elif ((xlen <= 5.09 or ylen <= 5.09)):
                    cv2.putText(frame0, f'Grade: C', (980, 100),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)
                    cv2.putText(frame0, f'R/G: {str(r_ratio)}%', (980, 150),
                                cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)
                print(ratio)

            # add dimensions
            draw.add_text(frame0, f'{xlen:.2f}{unit_suffix}', x1-((x1-x2)/2),
                          min(y1, y2)-8, center=True, color='red')
            draw.add_text(
                frame0, f'Area: {carea:.2f}{unit_suffix}^2', x3, y2+8, center=True, top=True, color='red')
            if alen:
                draw.add_text(
                    frame0, f'Avg: {alen:.2f}{unit_suffix}', x3, y2+34, center=True, top=True, color='green')
            if x1 < width-x2:
                draw.add_text(frame0, f'{ylen:.2f}{unit_suffix}', x2+4,
                              (y1+y2)/2, middle=True, color='red')
            else:
                draw.add_text(
                    frame0, f'{ylen:.2f}{unit_suffix}', x1-4, (y1+y2)/2, middle=True, right=True, color='red')

    # -------------------------------
    # dimension mode
    # -------------------------------
    else:

        # small crosshairs
        draw.crosshairs(frame0, 5, weight=2, color='green')

        # mouse cursor lines
        draw.vline(frame0, mouse_raw[0], weight=1, color='green')
        draw.hline(frame0, mouse_raw[1], weight=1, color='green')

        # draw
        if mouse_mark:

            # locations
            x1, y1 = mouse_mark
            x2, y2 = mouse_now

            # convert to distance
            x1c, y1c = conv(x1, y1)
            x2c, y2c = conv(x2, y2)
            xlen = (abs(x1c-x2c))/10
            ylen = (abs(y1c-y2c))/10
            llen = hypot(xlen, ylen)
            alen = 0
            carea=0
            if max(xlen, ylen) > 0 and min(xlen, ylen)/max(xlen, ylen) >= 0.95:
                alen = (xlen+ylen)/2
            if xlen>ylen:
                carea = 3.14*xlen**2
            elif xlen<ylen:
                carea = 3.14*ylen**2

            # print distances
            text.append('')
            text.append(f'X LEN: {xlen:.2f}{unit_suffix}')
            text.append(f'Y LEN: {ylen:.2f}{unit_suffix}')
            text.append(f'L LEN: {llen:.2f}{unit_suffix}')

            # convert to plot locations
            x1 += cx
            x2 += cx
            y1 *= -1
            y2 *= -1
            y1 += cy
            y2 += cy
            x3 = x1+((x2-x1)/2)
            y3 = max(y1, y2)

            # line weight
            weight = 1
            if key_flags['lock']:
                weight = 2

            # plot
            draw.rect(frame0, x1, y1, x2, y2, weight=weight, color='red')
            draw.line(frame0, x1, y1, x2, y2, weight=weight, color='green')

            #####################
            # RGB and Grading
            #####################

            # setting values for base colors
            b = frame0[:, :, :1]
            g = frame0[:, :, 1:2]
            r = frame0[:, :, 2:]

            # computing the mean
            b_mean = np.mean(b)
            g_mean = np.mean(g)
            r_mean = np.mean(r)

            # setting upper limit & lower limit
            b_bawah = 0.74
            range_ab = 0.48

            ratio = r_mean/g_mean
            #persen = ((ratio-b_bawah)*100)/range_ab
            r_ratio = round(ratio, 2)

            # add Grading and RGB
            if (xlen > 7.10 or ylen > 7.10):
                cv2.putText(frame0, f'Grade: A', (980, 100),
                            cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)
                cv2.putText(frame0, f'R/G: {str(r_ratio)}%', (980, 150),
                            cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)                            

            elif ((xlen >= 6.10 or ylen >= 6.10)) & ((xlen <= 7.09 or ylen <= 7.09)):
                cv2.putText(frame0, f'Grade: B', (980, 100),
                            cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)
                cv2.putText(frame0, f'R/G: {str(r_ratio)}%', (980, 150),
                            cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)

            elif ((xlen >= 5.10 or ylen >= 5.10)) & ((xlen <= 6.09 or ylen <= 6.09)):
                cv2.putText(frame0, f'Grade: C', (980, 100),
                            cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)
                cv2.putText(frame0, f'R/G: {str(r_ratio)}%', (980, 150),
                            cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)

            elif ((xlen >= 4.10 or ylen >= 4.10)) & ((xlen <= 5.09 or ylen <= 5.09)):
                cv2.putText(frame0, f'Grade: D', (980, 100),
                            cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)
                cv2.putText(frame0, f'R/G: {str(r_ratio)}%', (980, 150),
                            cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)

            else:
                cv2.putText(frame0, f'Grade: Abnormal', (980, 100),
                            cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)
                cv2.putText(frame0, f'R/G: {str(r_ratio)}%', (980, 150),
                            cv2.FONT_HERSHEY_COMPLEX, 1, (128, 0, 0), 2)
            print(ratio)

            # add dimensions -> kalo pake mouse
            draw.add_text(frame0, f'{xlen:.2f} cm', x1-((x1-x2)/2),
                          min(y1, y2)-8, center=True, color='red')
            draw.add_text(
                frame0, f'Area: {carea:.2f} cm^2', x3, y3+8, center=True, top=True, color='red')
            if alen:
                draw.add_text(
                    frame0, f'Avg: {alen:.2f}', x3, y3+34, center=True, top=True, color='green')
            if x2 <= x1:
                draw.add_text(frame0, f'{ylen:.2f} cm', x1+4,
                              (y1+y2)/2, middle=True, color='red')
                draw.add_text(frame0, f'{llen:.2f} cm',
                              x2-4, y2-4, right=True, color='green')
            else:
                draw.add_text(
                    frame0, f'{ylen:.2f} cm', x1-4, (y1+y2)/2, middle=True, right=True, color='red')
                draw.add_text(frame0, f'{llen:.2f} cm',
                              x2+8, y2-4, color='green')

    # add usage key
    text.append('')
    text.append(f'Q = QUIT')
    if key_flags['auto']:
        text.append(f'N = NORMALIZE')
        text.append(f'P = MIN-PERCENT')
        text.append(f'T = THRESHOLD')
        text.append('')
        text.append(f'FRUIT: ')
        text.append(f'J = JERUK')
        text.append(f'L = LEMON')
        text.append('')
        text.append(f'A = BACK')
    elif key_flags['config']:
        text.append(f'S = SET RULLER-SCALE')
        text.append('')
        text.append(f'C = BACK')
    else :
        text.append(f'A = AUTO-MODE')
        text.append(f'C = CONFIG-MODE')


    # draw top-left text block
    draw.add_text_top_left(frame0, text)

    # display
    cv2.imshow(framename, frame0)

    # key delay and action
    key = cv2.waitKey(1) & 0xFF

    if key in (27, 113):
        break

    # key data
    elif key not in (-1, 255):
        key_event(key)

camera.stop()
cv2.destroyAllWindows()
exit()