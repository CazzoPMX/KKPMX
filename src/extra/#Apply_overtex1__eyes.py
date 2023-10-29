import sys,os,re
import cv2
import json
import blend_modes
import numpy as np

try:
	import kkpmx_image_lib as imglib
except ImportError as eee:
	from . import kkpmx_image_lib as imglib

DisplayWithAspectRatio   = imglib.DisplayWithAspectRatio
DisplayWithAspectRatio_f = imglib.DisplayWithAspectRatio_f

args = sys.argv[1:]

def TryLoadJson(idx, _tuple=False, _array=False):
	try: return imglib.TryLoadJson(args[idx], _tuple, _array)
	except:
		args2 = [ args[0], args[1] + args[2] + args[3], args[4], args[5], args[6], args[7] ]
		return imglib.TryLoadJson(args2[idx], _tuple, _array)

#-------------
pathMain  = args[0]
data      = TryLoadJson(1, True)
verbose   = False#data["showinfo"]
hlPower   = data["highlight"]
def saveEval(tag, _def): return _def if (re.match(r"\([\d,\.\- ]+\)", tag) is None) else eval(tag)
offset    = saveEval(data["offset"], (0, 0))
scale     = saveEval(data["scale"],  (1, 1))
hlOne     = len(args[2]) > 0
hlTwo     = len(args[4]) > 0
#-------------
show      = False
opt       = imglib.makeOptions(locals())
#-------------
if hlOne:
	pathHL   = args[2]
	if len(pathHL) == 0: hlOne = False
	#else: hlOne = os.path.exists(pathHL)
	if hlOne:
		hldata   = TryLoadJson(3, False, True)
		hlColor  = hldata["color"]
		try: hlAlpha    = float(hldata["alpha"])
		except: hlAlpha = 1
if hlTwo:
	pathHL2  = args[4]
	if len(pathHL2) == 0: hlTwo = False
	#else: hlTwo = os.path.exists(pathHL2)
	if hlTwo:
		hldata   = TryLoadJson(5, False, True)
		hlColor2 = hldata["color"]
		try: hlAlpha2    = float(hldata["alpha"])
		except: hlAlpha2 = 1
#-------------
if verbose: print(("\n=== Running overtex1(Eyes) Script with arguments:" + "\n-- %s" * len(args)) % tuple(args))
#-------------
if hlOne == False and hlTwo == False: print("> No valid Highlights defined -- Only apply scale & offset")
#elif verbose: print(f"> Highlight State: HL1={hlOne} at {hlAlpha}, HL2={hlTwo*100}% at {hlAlpha2*100}%")
#-------------

image     = imglib.TryLoadImage(pathMain, "MainTex")
try:
	if hlOne:
		highlight = imglib.resize(imglib.TryLoadImage(pathHL, "Highlight 1"), image)
		hlAlpha   = hlAlpha * hlPower
		color     = imglib.getColorMask(opt, highlight, hlColor, "HL1")
		highlight = imglib.blend_segmented(blend_modes.overlay, color, highlight, 1)
except:
	print("> No valid 1st Highlight defined")
	hlOne = False
try:
	if hlTwo:
		highlight2 = imglib.resize(imglib.TryLoadImage(pathHL2, "Highlight 2"), image)
		hlAlpha2   = hlAlpha2 * hlPower
		color      = imglib.getColorMask(opt, highlight2, hlColor2, "HL2")
		highlight2 = imglib.blend_segmented(blend_modes.overlay, color, highlight2, 1)
except:
	print("> No valid 2nd Highlight defined")
	hlTwo = False
	
if hlOne: image = imglib.blend_segmented(blend_modes.normal, image, highlight, hlAlpha)
if hlTwo: image = imglib.blend_segmented(blend_modes.normal, image, highlight2, hlAlpha2)

DisplayWithAspectRatio(opt, 'Normal', image, 256)

blackCorner = sum(image[0, 0, :])
def check_if_black(_tmp, _hh, _ww, isVert):
	if _hh < 0: raise Exception("h too small")
	if _ww < 0: raise Exception("w too small")
	if sum(_tmp[_hh, _ww, :]) != blackCorner:
		#if isVert: print(f"The VertCenter({_hh} x> {_ww}) is not black! Cut off too much")
		#else:      print(f"The HortCenter({_ww} <x {_hh}) is not black! Cut off too much")
		return True
	return False
#-------------
#### Apply Scale
orgShape = image.shape
width  = int(orgShape[1] / scale[0])
height = int(orgShape[0] / scale[1])
dw = int((width  - orgShape[1]) / 2) #-int(dw/2) is the skip needed to reduce it into PMX size
dh = int((height - orgShape[0]) / 2)

image = cv2.resize(image, dsize=(width, height), interpolation=cv2.INTER_AREA)
DisplayWithAspectRatio(opt, 'Scaled', image, 256)
if verbose:
	print(f">[Scaled]: {orgShape} to {image.shape} -- Using {scale} -> h,w={(height, width)}")

#### Fit back to original size
tmp = np.zeros(orgShape, dtype='uint8')
#if show: k = cv2.waitKey(0) & 0xFF
if verbose:
	#orgShape: Original Image \\ Resized according to (orgShape x Scale) \\ center 
	print(f"{orgShape} vs {image.shape} -[w{(dw,dh)}h]- {tmp[-dh+1:dh, -dw+1:dw, :].shape} {image[-dh+1:dh, -dw+1:dw, :].shape}")

####--- Adjust Scale-Reduction to bigger initial Iris Picture
#-- So far only for checks with dw smaller than 1 (test if other IFs are needed)
if (dw < 0):# and scale[0] > 1 and scale[1] != 1: ## Image is bigger than original
	##TESTED WITH: dw < 0, scale= (> 1, !=1) :: (2.1, 1.8), offset(0.0, -0.05)
	spotV = int(image.shape[0] / 2)
	walkH = -int(dw/2)
	if check_if_black(image, spotV, walkH, True):
		idx = 0
		while(check_if_black(image, spotV, walkH, True)):
			idx = idx + 1
			walkH = walkH - 1
		if verbose: print(f"Reached end at {idx}: {dw} -> {dw+idx+idx}")#{dw-idx-idx}")
		dw = dw + (idx*2)
## Adhoc assumption for height
if (dh < 0):
	walkV = -int(dh/2)
	spotH = int(image.shape[1] / 2)
	if check_if_black(image, walkV, spotH, False):
		idx = 0
		while(check_if_black(image, walkV, spotH, False)):
			idx = idx + 1
			walkV = walkV - 1
		if verbose: print(f"Reached end at {idx}: {dh} -> {dh+idx+idx}")#{dw-idx-idx}")
		dh = dh + (idx*2)

try:
	if (dw > 0):    ## Image became smaller, so just cut it out
		image = image[:, dw:-dw, :]
	elif (dw < 0):  ## Image became bigger, so do magic
		if scale[0] > 1: ## 1 off if (big, 1.0) \\ Cut off if (big, big)
			## Go further outwards because width increased
			if scale[1] != 1: tmp = image[:, -int(dw/2):int(dw/2), :]
			else: ## TODO figure out magic again
				print(f"Case: dw < 0, scale= (> 1, ==1)")
				inSh = image.shape
				outSh = tmp[:, -dw:dw, :].shape
				if   outSh[1] == inSh[1]:   tmp[:, -dw:dw, :] = image
				elif outSh[1] == inSh[1]+1: tmp[:, -dw+1:dw, :] = image ## with (1.1, 1.0) on 512,512
				elif outSh[1] == inSh[1]-1: tmp[:, -dw-1:dw, :] = image
		else:
			print(f"Case: dw < 0, scale= (<=1, ???)")
			tmp[:, -dw+1:dw, :] = image
		image = tmp
except:
	print(f"- orgShape: {orgShape}")
	print(f"- img:      {image.shape}")
	print(f"- dw:       {dw}")
	print(f"- scale:    {scale}")
	raise
if verbose: print(f">Resized[H]: {image.shape}")

DisplayWithAspectRatio(opt, 'Resized H', image, 256)
if show: k = cv2.waitKey(0) & 0xFF

tmp = np.zeros(orgShape, dtype='uint8')
if (dh != 0):
	if (dh > 0):   image = image[dh:-dh, :, :]
	elif (dh < 0):
		if scale[1] > 1: ## 1 off error in (1.0, big)
			if scale[0] != 1: ## oversized when both are big
				tmp = image[-int(dh/2):int(dh/2), :, :]
			else:
				try: tmp[-dh:dh, :, :]   = image
				except: tmp[-dh+1:dh, :, :]   = image
		else:     tmp[-dh+1:dh, :, :] = image
		image = tmp

DisplayWithAspectRatio(opt, 'Resized V', image, 256)
if verbose: print(f">Resized[Y]: {image.shape}")

#### Restore original size
padX = 0; padY = 0; tmp = np.zeros(orgShape, dtype='uint8')
if image.shape[0] < orgShape[0]: padY = int((orgShape[0] - image.shape[0])/2) ## for (*, big)
if image.shape[1] < orgShape[1]: padX = int((orgShape[1] - image.shape[1])/2) ## for (big,*)
if verbose: print(f">Restore to Org: {image.shape} --> Pad Y={padY}, X={padX}") ## Should say the exact same thing
changed = False
try:
	#print(f"[Y:Y,X+1:X] tmp:{tmp.shape} vs. {image.shape}")
	if padX > 0 and padY > 0: tmp[padY:-padY,padX+1:-padX,:] = image; changed=True
	elif padX > 0:            tmp[:,padX+1:-padX,:]          = image; changed=True
	elif padY > 0:            tmp[padY:-padY,:,:]            = image; changed=True
except: ## Fixing rare one-off cases
	try:
		#print(f"[Y:Y,X:X] tmp:{tmp.shape} vs. {image.shape}")
		if padX > 0 and padY > 0: tmp[padY:-padY,padX:-padX,:] = image; changed=True
		elif padX > 0:            tmp[:,padX:-padX,:]          = image; changed=True
		elif padY > 0:            tmp[padY:-padY,:,:]          = image; changed=True
	except:
		try:
			#print(f"[Y-1:Y,X:X] tmp:{tmp.shape} vs. {image.shape}")
			if padX > 0 and padY > 0: tmp[padY+1:-padY,padX+1:-padX,:] = image; changed=True
			elif padX > 0:            tmp[:,padX+1:-padX,:]            = image; changed=True
			elif padY > 0:            tmp[padY+1:-padY,:,:]            = image; changed=True
		except:
			try:
				#print(f"[Y-1:Y,X:X] tmp:{tmp.shape} vs. {image.shape}")
				if padX > 0 and padY > 0: tmp[padY+1:-padY,padX:-padX,:] = image; changed=True
				elif padX > 0:            tmp[:,padX:-padX,:]            = image; changed=True
				elif padY > 0:            tmp[padY+1:-padY,:,:]          = image; changed=True
			except:
				print(f"[??????] tmp:{tmp.shape} vs. {image.shape}")
				raise
		
DisplayWithAspectRatio(opt, 'Fixed', tmp, 256)
if changed: image = tmp

#### Apply Offset
tmp = np.zeros(image.shape, dtype='uint8')
tmpOff = offset[1] if offset[1] < 0 else (offset[1] - 0.1)
factorY = int(image.shape[0] * tmpOff) # Sink Eyes by 1/20 per default, to reflect Model position
if factorY != 0:
	invY = factorY * -1
	tmp[:invY, :, :]  = image[ factorY:, :, :]
	tmp[ invY:, :, :] = image[:factorY, :, :]
	image = tmp

tmp = np.zeros(image.shape, dtype='uint8')
factorX = int(image.shape[1] * offset[0])
#print(f"Offset: {offset} -> X:{factorX}, Y:{factorY}")
if factorX != 0:
	invX = factorX * -1
	tmp[:, :invX, :]  = image[:,  factorX:, :]
	tmp[:,  invX:, :] = image[:, :factorX, :]
	image = tmp

DisplayWithAspectRatio(opt, 'Offset', image, 256)

if show: k = cv2.waitKey(0) & 0xFF
### Write out final image
outName = pathMain[:-4] + "_pyHL.png"
imglib.TryWriteImage(outName, image)
print("Wrote output image at\n" + outName)