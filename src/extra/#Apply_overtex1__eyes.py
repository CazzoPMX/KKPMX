import sys
import cv2
import json
import blend_modes

try:
	import kkpmx_image_lib as imglib
except ImportError as eee:
	from . import kkpmx_image_lib as imglib

args = sys.argv[1:]
#-------------
pathMain  = args[0]
hlPower   = json.loads(args[1])
hlOne     = len(args[2]) > 0
hlTwo     = len(args[4]) > 0
#-------------
if hlOne:
	pathHL   = args[2]
	hlAlpha  = json.loads(args[3])
	if len(pathHL) == 0: hlOne = False
if hlTwo:
	pathHL2  = args[4]
	hlAlpha2 = json.loads(args[5])
	if len(pathHL2) == 0: hlTwo = False
#-------------
if hlOne == False and hlTwo == False: exit()
#-------------
print(("\n=== Running Body overtex1 Script with arguments:" + "\n-- %s" * len(args)) % tuple(args))

image     = cv2.imread(pathMain, cv2.IMREAD_UNCHANGED)
if hlOne:
	highlight = imglib.resize(cv2.imread(pathHL, cv2.IMREAD_UNCHANGED), image)
	hlAlpha   = hlAlpha * hlPower
if hlTwo:
	highlight2 = imglib.resize(cv2.imread(pathHL2, cv2.IMREAD_UNCHANGED), image)
	hlAlpha2   = hlAlpha2 * hlPower

if hlOne: image = imglib.blend_segmented(blend_modes.addition, image, highlight, hlAlpha)
if hlTwo: image = imglib.blend_segmented(blend_modes.addition, image, highlight2, hlAlpha2)

### Write out final image
outName = pathMain[:-4] + "_pyHL.png"
cv2.imwrite(outName, image)
print("Wrote output image at\n" + outName)