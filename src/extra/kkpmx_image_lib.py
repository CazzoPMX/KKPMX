# Cazoo - 2021-05-20
# This code is free to use and re-distribute, but I cannot be held responsible for damages that it may or may not cause.
#####################
import sys
import cv2
import numpy as np
import blend_modes
import gc

def makeOptions(_opt):
	return {
		"alpha": _opt.get("alpha", 64 / 255),
		"show":  _opt.get("show", False),
		"mode":  _opt.get("mode", "Additive"),
		"scale": _opt.get("scale", 1),
	}

######
## Display
######

def printImageStats(img):
	print(type(img))
	print("shape={}, dtype={}".format(img.shape, img.dtype))

#### https://stackoverflow.com/questions/35180764/opencv-python-image-too-big-to-display
#> rewrote to be "cv2.show" instead of return
def DisplayWithAspectRatio_f(opt, title, _img, width=None, height=None, inter=cv2.INTER_AREA):
	if not opt["show"]: return
	if opt["scale"] == 1: img = _img#.astype("uint8")
	else:                 img = (_img * opt["scale"])#.astype("uint8")
	DisplayWithAspectRatio(opt, title, img, width, height, inter)

def DisplayWithAspectRatio(opt, title, _img, width=None, height=None, inter=cv2.INTER_AREA):
	if not opt["show"]: return
	img = _img.astype("uint8")
	dim = None
	(h, w) = img.shape[:2]

	if width is None and height is None:
		return
	if width is None:
		r = height / float(h)
		dim = (int(w * r), height)
	else:
		r = width / float(w)
		dim = (width, int(h * r))

	cv2.imshow(title, cv2.resize(img, dim, interpolation=inter))

######
## Helpers
######

def converter255(img, imgAlpha=None): ## read: [imgAlpha, cv2]
	if img.shape[2] == 4:
		#return (cv2.merge([img[:,:,0], img[:,:,1], img[:,:,2], img[:,:,3]]) / 255).astype(float)
		return img.astype(float)
	if imgAlpha is not None:
		return (cv2.merge([img[:,:,0], img[:,:,1], img[:,:,2], imgAlpha])).astype(float)
	#return (cv2.merge([img[:,:,0], img[:,:,1], img[:,:,2]]) / 255).astype(float)
	return img.astype(float)

def converterX(img, imgAlpha=None): ## read: [imgAlpha, cv2]
	if img.shape[2] == 4:
		#return (cv2.merge([img[:,:,0], img[:,:,1], img[:,:,2], img[:,:,3]]) / 255).astype(float)
		return (img / 255).astype(float)
	if imgAlpha is not None:
		return (cv2.merge([img[:,:,0], img[:,:,1], img[:,:,2], imgAlpha]) / 255).astype(float)
	#return (cv2.merge([img[:,:,0], img[:,:,1], img[:,:,2]]) / 255).astype(float)
	return (img / 255).astype(float)

def converterScaled(opt, img, imgAlpha=None, addAlpha=False): ## read: [imgAlpha, cv2]
	if img.shape[2] == 4:
		return (img / opt["scale"]).astype(float)
	if addAlpha and imgAlpha is None:
		imgAlpha = np.ones(img.shape[:2], dtype='uint8') * 255
	if imgAlpha is not None:
		imgBase = np.ones([img.shape[0], img.shape[1], 4], dtype='float') * 255
		imgBase[:,:,:3] = img.astype(float)
		imgBase[:,:,3] = imgAlpha
		#return (cv2.merge([img[:,:,0], img[:,:,1], img[:,:,2], imgAlpha]) / opt["scale"]).astype(float)
		return imgBase
	return (img / opt["scale"]).astype(float)
def converter(img, imgAlpha=None, addAlpha=False): return converterScaled({ "scale": 1}, img, imgAlpha, addAlpha)

def resize(imgSource, imgTarget, inter=cv2.INTER_AREA):
    if type(imgTarget) in [list,tuple]: shape = imgTarget
    else:                               shape = imgTarget.shape

    if (imgSource.shape[:2] != shape[:2]):
        target = shape
        source = imgSource.shape
        width  = int(round(source[1] * (target[1] / source[1])))
        height = int(round(source[0] * (target[0] / source[0])))
        #print("{} * ({} / {} = {}) == {}".format(source[1], target[1], source[1], target[1] / source[1], width))
        #print("{} * ({} / {} = {}) == {}".format(source[0], target[0], source[0], target[0] / source[0], height))
        return cv2.resize(imgSource, (width, height), interpolation=inter)
    return imgSource

def normalize_color(color): ## from: body_overtex1
	if type(color).__name__ == 'ndarray': color = color.tolist()
	if any([x > 1 for x in color]):
		if len(color) == 3: color.append(255)
		return color
	if len(color) == 3: color.append(1)
	return [ int(color[0]*255), int(color[1]*255), int(color[2]*255), int(color[3]*255) ]

def extendChannel(img, _alpha=None):
	""" Expand a single RGB-Channel into a full RGB canvas with optional Alpha."""
	if _alpha is None: _alpha = np.ones(img.shape[:2], dtype=img.dtype) * 255
	return cv2.merge([img, img, img, _alpha])

def extendAlpha(img):
	""" Add an empty canvas for a 2D Alpha channel. """
	tmp = np.ones(img.shape[:2], dtype="uint8") * 255
	return cv2.merge([tmp, tmp, tmp, img])

def resizeWithAspectRatio(_img, width=None, height=None):
	dim = None
	img = _img.astype("uint8")
	(h, w) = img.shape[:2]

	if width is None and height is None:
		return
	if width is None:
		r = height / float(h)
		dim = (int(w * r), height)
	else:
		r = width / float(w)
		dim = (width, int(h * r))
	return resize(_img, dim)

def get_blend_mode(blend_mode):
	""" See https://pythonhosted.org/blend_modes/ """
	if blend_mode in dir(blend_modes): return getattr(blend_modes, blend_mode)
	blendDict = {#		mode = "darken" ## Try: "mul" "diff" "nor"
		"normal": blend_modes.normal,
		"overlay": blend_modes.overlay,
		"add": blend_modes.addition,
		"lighten": blend_modes.lighten_only,
		"darken": blend_modes.darken_only,
		"mul": blend_modes.multiply,
		"diff": blend_modes.difference,
		"GExtract": blend_modes.grain_extract,
	}
	if blend_mode not in blendDict: raise Exception("Unknown blend_mode " + blend_mode)
	return blendDict[blend_mode]

def blend_segmented(blend_mode, main, mask, alpha):
	"""
	@param :blend_mode: str or Func
	@param :main:       -- Background image
	@param :mask:       -- Foreground image
	@param :alpha:      -- Opacity
	
	Applies the given blend_mode to @main and @mask, using @alpha as opacity.
	To save resources, images are processed in chunks of 1024x1024 
	"""
	if type(blend_mode) == str: blend_mode = get_blend_mode(blend_mode)
	gc.collect()
	_main = converter(main, addAlpha=True)
	_mask = converter(mask, addAlpha=True)
	def buildRange(axis, size):
		ret = []
		arr = [x for x in range(0, axis, size)]
		while len(arr) > 1:
			val = arr.pop(0)
			ret.append(slice(val, arr[0]))
		## we want the end + last is always omitted
		ret.append(slice(arr[0], axis))
		return ret
	height = buildRange(_main.shape[0], 1024)
	width = buildRange(_main.shape[1], 1024)
	image = np.zeros(_main.shape, dtype='float')
	for y in height:
		for x in width:
			image[y,x,:] = blend_mode(_main[y,x,:], _mask[y,x,:], alpha)
	return image

def ensureAlpha(img, imgAlpha=None):
	if len(img.shape) == 2: return extendChannel(img, imgAlpha)
	if img.shape[2] == 4: return img
	if not imgAlpha:
		imgAlpha = np.ones(img.shape[:2], dtype='uint8') * 255
	return cv2.merge([img[:,:,0], img[:,:,1], img[:,:,2], imgAlpha])

######
## Main
######

def applyColor(opt, _mask, _colArr, tag): ## read: [show, np, cv2, mode, alpha, beta], write: [bitmaskArr]
	"""
	_mask :: One Color channel of [imgMask] as BW, extended into 3-Channel
	:: Only cv2.show & cv2.addWeighted need it as 3-Channel + Convenient for 'Additive'
	_colArr :: An [ R, G, B ] Array; Alpha is discarded
	
	Given a mask [0], apply an RGB color [1] where '[0].pixel > 0'
	"""
	if opt["show"]: print(_colArr)
	if len(_colArr) == 3: _colArr.push(1)

	## Make a white image to create a mask for "above 0"
	bitmask = np.ones(_mask.shape[:2], dtype="uint8") * 255
	bitmask[:,:] = (_mask[:,:,3] != 0)
	#if len(_colArr) == 4:
	#	bitmask = cv2.merge([bitmask*255, bitmask*255, bitmask*255, bitmask*255])
	#else:
	
	#print(bitmask.dtype)
	#print(_mask.dtype)
	bitmaskCol = cv2.merge([bitmask*255, bitmask*255, bitmask*255, bitmask*255])
	bitmaskNon = cv2.merge([(1-bitmask)*255, (1-bitmask)*255, (1-bitmask)*255, (1-bitmask)*255])
	
	bitmask = bitmaskCol
	# (_mask[:,:,3]*255).astype("uint8")
	DisplayWithAspectRatio(opt, 'bitmask'+tag, bitmask.astype("uint8"), 256) ## Where to add color
	#bitmaskArr.append(bitmask)
	
	#print("{},{},{}".format(type(bitmaskNon),bitmaskNon.shape, bitmaskNon.dtype))
	#print("{},{},{}".format(type(_mask),_mask.shape, _mask.dtype))
	mask_rest  = np.bitwise_and(bitmaskNon, _mask.astype("uint8"))
	
	## Create an image of this color
	colImg0 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[0]
	colImg1 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[1]
	colImg2 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[2]
	colImg3 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[3]
	#if _mask.shape[2] == 4: 
	#	colImg3 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[3]
	#	colImg = cv2.merge([colImg2, colImg1, colImg0, colImg3]) ## Apparently the KK-RGB is as BGR ???
	#	#colImg = cv2.merge([colImg0, colImg1, colImg2, colImg3]) ## Apparently the KK-RGB is as BGR ???
	#else:
	colImg = cv2.merge([colImg2, colImg1, colImg0, colImg3]) ## Apparently the KK-RGB is as BGR ???
	DisplayWithAspectRatio(opt, 'Color'+tag,     colImg.astype("uint8"), 256)## A canvas of this Color
	DisplayWithAspectRatio(opt, 'ColorMask'+tag, _mask.astype("uint8"), 256)## How the channel looks
	
	## Apply that color
	_maskA = None
	#if _mask.shape[2] == 4: _maskA = _mask[:,:,3]# * (_colArr[3]/255)
	#testOutModes(opt, converter(opt, colImg), converter(opt, _mask), 256, True)
	if opt["mode"] == "Overlay":
		#_mask = cv2.addWeighted(_mask, 1 - opt["alpha"], colImg, opt["alpha"], 0)
		#_mask = cv2.addWeighted(_mask, 1 - opt["alpha"], colImg, opt["alpha"], 0)
		_mask = cv2.addWeighted(_mask[:,:,:], 1 - opt["alpha"], colImg, opt["alpha"], 0)
	elif opt["mode"] == "Diff":
		_mask = blend_modes.difference(converter(opt, colImg), converter(opt, _mask), opt["alpha"]) * 255

	elif opt["mode"] == "Additive":
		_mask[:,:,0] = ((_mask[:,:,0] / 255) * (colImg[:,:,0]))
		_mask[:,:,1] = ((_mask[:,:,1] / 255) * (colImg[:,:,1]))
		_mask[:,:,2] = ((_mask[:,:,2] / 255) * (colImg[:,:,2]))
		#_mask[:,:,3] = ((_mask[:,:,3] / 255) * (colImg[:,:,3]))
		#testOutModes(opt, converter(opt, colImg), converter(opt, _mask), 256)
		#_mask = blend_modes.addition(converter(opt, colImg), converter(opt, _mask), opt["alpha"]) * 255
	if opt["show"]: cv2.imshow('Unmasked + Color:'+tag, _mask)
	
	#if _maskA is not None:
	#	_mask = cv2.merge([_mask[:,:,0], _mask[:,:,1], _mask[:,:,2], _maskA])
	
	_mask = _mask.astype("uint8")
	
	## Apply mask again
	#print("{},{},{}".format(type(bitmask),bitmask.shape, bitmask.dtype))
	#print("{},{},{}".format(type(_mask),_mask.shape, _mask.dtype))
	mask_color = np.bitwise_and(bitmask, _mask)
	
	return blend_modes.addition(converter(opt, mask_color), converter(opt, mask_rest), 1) * 255

def applyColor_org(opt, _mask, _colArr, tag): ## Original from [ColorMask]
	"""
	_mask :: One Color channel of [imgMask] as BW, extended into 3-Channel
	:: Only cv2.show & cv2.addWeighted need it as 3-Channel + Convenient for 'Additive'
	_colArr :: An [ R, G, B ] Array; Alpha is discarded
	
	Given a mask [0], apply an RGB color [1] where '[0].pixel > 0'
	"""
	if opt["show"]: print(_colArr)
	#tag = str(_colArr[0])
	## Make a white image to create a mask for "above 0"
	bitmask = np.ones(_mask.shape[:2], dtype="uint8") * 255
	bitmask[:,:] = (_mask[:,:,0] != 0)
	#if len(_colArr) == 4:
	#	bitmask = cv2.merge([bitmask*255, bitmask*255, bitmask*255, bitmask*255])
	#else:
	bitmask = cv2.merge([bitmask*255, bitmask*255, bitmask*255])
	if opt["show"]: cv2.imshow('bitmask'+tag, bitmask) ## Where to add color
	#bitmaskArr.append(bitmask)
	
	## Create an image of this color
	colImg0 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[0]
	colImg1 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[1]
	colImg2 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[2]
	#if _mask.shape[2] == 4: 
	#	colImg3 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[3]
	#	colImg = cv2.merge([colImg2, colImg1, colImg0, colImg3]) ## Apparently the KK-RGB is as BGR ???
	#	#colImg = cv2.merge([colImg0, colImg1, colImg2, colImg3]) ## Apparently the KK-RGB is as BGR ???
	#else:
	colImg = cv2.merge([colImg2, colImg1, colImg0]) ## Apparently the KK-RGB is as BGR ???
	if opt["show"]: cv2.imshow('Color'+tag, colImg)  ## A canvas of this Color
	if opt["show"]: cv2.imshow('ColorMask'+tag, _mask) ## How the channel looks
	
	## Apply that color
	_maskA = None
	#if _mask.shape[2] == 4: _maskA = _mask[:,:,3]# * (_colArr[3]/255)
	if opt["mode"] == "Overlay":
		#_mask = cv2.addWeighted(_mask, 1 - opt["alpha"], colImg, opt["alpha"], 0)
		#_mask = cv2.addWeighted(_mask, 1 - opt["alpha"], colImg, opt["alpha"], 0)
		_mask = cv2.addWeighted(_mask[:,:,:3], 1 - opt["alpha"], colImg, opt["alpha"], 0)
	elif opt["mode"] == "Additive":
		#print(_colArr[0], " -> ", _colArr[0] / 255)
		#print((_mask[0,0,:]))
		#print((_mask[0,0,:] / 255))
		#print((_mask[0,0,:] / 255) * _colArr)
		#print((_mask[0,0,:]) * (_colArr / 255))
		
		_mask[:,:,0] = ((_mask[:,:,0] / 255) * (colImg[:,:,0]))
		_mask[:,:,1] = ((_mask[:,:,1] / 255) * (colImg[:,:,1]))
		_mask[:,:,2] = ((_mask[:,:,2] / 255) * (colImg[:,:,2]))
		#testOutModes(opt, converter(opt, colImg), converter(opt, _mask), 256)
		#_mask = blend_modes.addition(converter(opt, colImg), converter(opt, _mask), opt["alpha"]) * 255
	if opt["show"]: cv2.imshow('Unmasked + Color:'+tag, _mask)
	
	#if _maskA is not None:
	#	_mask = cv2.merge([_mask[:,:,0], _mask[:,:,1], _mask[:,:,2], _maskA])
	
	_mask = _mask.astype("uint8")
	
	## Apply mask again
	return np.bitwise_and(bitmask, _mask)

def getColorMask(opt, _mask, _colArr, tag="", useKKOrder=True): ## from [overtex]
	"""
	_mask :: One Color channel of [imgMask] as BW, extended into 3-Channel
	:: Only cv2.show & cv2.addWeighted need it as 3-Channel + Convenient for 'Additive'
	_colArr :: An [ R, G, B ] Array; Alpha is discarded
	
	Given a mask [0], create a colImg based on an RGBA color [1] that is affected by [0].alpha
	"""
	if opt["show"]: print(_colArr)
	_colArr = normalize_color(_colArr)
	if len(_mask.shape) == 2: _mask = extendAlpha(_mask)
	elif _mask.shape[2] == 1: _mask = extendAlpha(_mask)
	
	## Create an image of this color
	colImg0 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[0]
	colImg1 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[1]
	colImg2 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[2]
	colImg3 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[3]
	
	## Apparently the KK-RGB is as BGR, so do that
	if useKKOrder: colImg = cv2.merge([colImg2, colImg1, colImg0, colImg3])
	else:          colImg = cv2.merge([colImg0, colImg1, colImg2, colImg3])
	DisplayWithAspectRatio(opt, 'Color'+tag,     colImg.astype("uint8"), 256)## A canvas of this Color

	mask_color = np.bitwise_and(extendAlpha(_mask[:,:,3]), colImg)

	DisplayWithAspectRatio(opt, 'ColorMaskAlpha'+tag, mask_color, 256)## A canvas of this Color
	return mask_color

def getColorImg(opt, _mask, _colArr, tag="", useKKOrder=False): ## from [overtex]
	"""
	_mask :: The Alpha Channel of an image
	:: Only cv2.show & cv2.addWeighted need it as 3-Channel + Convenient for 'Additive'
	_colArr :: An [ R, G, B ] Array; Alpha is discarded
	
	Given a mask [0], create a colImg based on an RGBA color [1] that is affected by [0].alpha
	"""
	if opt["show"]: print(_colArr)
	_colArr = normalize_color(_colArr)
	if len(_mask.shape) > 2: _mask = _mask[:,:,-1]
	
	## Create an image of this color
	colImg0 = np.ones(_mask.shape, dtype="uint8") * _colArr[0]
	colImg1 = np.ones(_mask.shape, dtype="uint8") * _colArr[1]
	colImg2 = np.ones(_mask.shape, dtype="uint8") * _colArr[2]
	colImg3 = _mask
	
	## Apparently the KK-RGB is as BGR, so do that
	if useKKOrder: colImg = cv2.merge([colImg2, colImg1, colImg0, colImg3])
	else:          colImg = cv2.merge([colImg0, colImg1, colImg2, colImg3])
	DisplayWithAspectRatio(opt, 'ColorImg'+tag,     colImg.astype("uint8"), 256)

	return colImg

def getColorWithAlpha(opt, _mask, _colArr, tag="", useKKOrder=False): ## from [overtex]
	"""
	_mask :: One Color channel of [imgMask] as BW, extended into 3-Channel
	:: Only cv2.show & cv2.addWeighted need it as 3-Channel + Convenient for 'Additive'
	_colArr :: An [ R, G, B ] Array; Alpha is discarded
	
	Given a mask [0], create a colImg based on an RGBA color [1] that is affected by [0].alpha
	"""
	if opt["show"]: print(_colArr)
	_colArr = normalize_color(_colArr)
	if len(_mask.shape) == 2: _mask = extendAlpha(_mask)
	elif _mask.shape[2] == 1: _mask = extendAlpha(_mask)
	
	## Create an image of this color
	colImg0 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[0]
	colImg1 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[1]
	colImg2 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[2]
	colImg3 = np.ones(_mask.shape[:2], dtype="uint8") * _colArr[3]
	
	## Apparently the KK-RGB is as BGR, so do that
	if useKKOrder: colImg = cv2.merge([colImg2, colImg1, colImg0, colImg3])
	else:          colImg = cv2.merge([colImg0, colImg1, colImg2, colImg3])
	DisplayWithAspectRatio(opt, 'Color'+tag,     colImg.astype("uint8"), 256)

	return colImg

def colorizeBitmask(opt, _mask, _colArr, tag=""):
	"""
	If the image is already a bitmask, using [overlay] of Mask onto the color achieves the same effect.
	"""
	color = getColorMask(opt, _mask, _colArr, tag)
	return blend_segmented(blend_modes.overlay, color, _mask, 1)

## Copy [_overlay] in the [_mask]ed area of [_base]
def combineWithBitmask(opt, _base, _overlay, _mask):
	if (_base.shape[2] == 4): _mask = ensureAlpha(_mask)
	return cv2.copyTo(_overlay, _mask.astype("uint8"), _base)

def merge_channelsOpt(opt, _img, arr, name='Merged'):
	img = merge_channels(_img, arr)
	DisplayWithAspectRatio(opt, name, img, 256)
	return img
def merge_channels(_img, arr): ## in[(:,:,3+), List(3)], out[(:,:)]
	## https://stackoverflow.com/questions/23224976/convert-image-to-grayscale-with-custom-luminosity-formula
	#arr = [1,0,0] # Gives blue channel all the weight
	#arr = [0.114, 0.587, 0.299] # for standard gray conversion,
	m = np.array(arr).reshape((1,3))
	return cv2.transform(img[:,:,:3], m)

def filter_blue(_img, arr):
	#https://stackoverflow.com/questions/22588146/tracking-white-color-using-python-opencv
	hsv = cv2.cvtColor(_img, cv2.COLOR_BGR2HSV)
	## [Value=Black -> Color \\ Sat=Gray -> Color]
	# define range of blue color in HSV
	lower_blue = np.array([110,100,100])
	upper_blue = np.array([130,255,255])
	
	# for white color
	lower_white = np.array([0,0,168])
	upper_white = np.array([172,111,255])
	
	# Threshold the HSV image to get only blue colors
	mask = cv2.inRange(hsv, lower_blue, upper_blue)
	# Bitwise-AND mask and original image
	return cv2.bitwise_and(_img, _img, mask=mask)

## Sets all black-ish pixels to 0,0,0 for binary masking
def smooth_black(_img):
	#https://stackoverflow.com/questions/22588146/tracking-white-color-using-python-opencv
	hsv = cv2.cvtColor(_img, cv2.COLOR_BGR2HSV)
	## [Value=Black -> Color \\ Sat=Gray -> Color]
	# define color range in HSV
	lower_range = np.array([0,0,48])
	upper_range = np.array([180,255,255])
	
	# Threshold the HSV image
	mask = cv2.inRange(hsv, lower_range, upper_range)
	# Bitwise-AND mask and original image
	return cv2.bitwise_and(_img, _img, mask=mask)


######
## Small
######

def convert_to_BW(image, full=True): ## OpenCV default is BGR
	convCh = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
	if not full: return convCh
	return cv2.merge([convCh, convCh, convCh, image[:,:,3]])

#""" Add image to itself as Alpha """
def apply_alpha_BW(opt, img): return converterScaled(opt, img, convert_to_BW(img, False), True).astype("uint8")

def invert(image):
	return cv2.merge([255 - image[:,:,0], 255 - image[:,:,1], 255 - image[:,:,2], image[:,:,3]])

def invert_f(image):
	return cv2.merge([1 - image[:,:,0], 1 - image[:,:,1], 1 - image[:,:,2], image[:,:,3]])

def getBitmask(image, show=False, tag="", binary=False):
	## Make a white image to create a mask for "above 0"
	bitmask = np.ones(image.shape[:2], dtype="uint8") * 255
	#if binary:
	#	bitmask[:,:] = (image[:,:,0] != 0)
	#	bitmask = cv2.merge([bitmask*255, bitmask*255, bitmask*255])
	#else:
	bitmask[:,:] = (image[:,:] != 0)
	if show: cv2.imshow('bitmask'+tag, bitmask) ## Where to add color
	## Apply mask with np.bitwise_and(bitmask, _mask)
	if binary: return (bitmask).astype("uint8")
	return (bitmask * 256).astype("uint8")

def negate(image):   return (image + 256) * (-1) + 512
def negate_f(image): return (image + 1) * (-1) + 2

def BGR_to_HSV(arr): return cv2.cvtColor(np.uint8([[arr[:3]]]), cv2.COLOR_BGR2HSV)[0,0,:]
def arrCol(arr, _col): return cv2.cvtColor(np.uint8([[arr[:3]]]), _col)[0,0,:]
def RGB_to_real_HSV(arr):
	cv2_HSV = arrCol(arr, cv2.COLOR_RGB2HSV)
	cv2_HSV[0] *= 2        ## 180 -> 360
	cv2_HSV[1] *= (1/2.55) ## 255 -> 100
	cv2_HSV[2] *= (1/2.55) ## 255 -> 100
	return cv2_HSV

def printFlags(): print([i for i in dir(cv2) if i.startswith('COLOR_')])


def my_RGB_to_HSV(_col):
	(R, G, B) = _col[:3]
	## <skip>: Make sure _col is 0..255
	RR = R / 255
	GG = G / 255
	BB = B / 255
	Cmax = max(RR, GG, BB)
	Cmin = min(RR, GG, BB)
	delta = Cmax - Cmin
	### prep
	hue = 0; sat = 0; val = 0
	### Hue
	if delta == 0: hue = 0
	elif Cmax == RR: hue = ((GG - BB)/delta) % 6
	elif Cmax == GG: hue = (BB - RR) / delta + 2
	elif Cmax == BB: hue = (RR - GG) / delta + 4
	hue *= 60
	if hue < 0: hue += 360
	### Saturation
	if Cmax == 0: sat = 0
	else: sat = delta / Cmax
	### Value
	val = Cmax
	## Convert from % to full number
	sat *= 100;
	val *= 100;
	return [hue, sat, val]


def change_hue(_img, _val): ## Using default order of BGR
	img_hsv = cv2.cvtColor(_img, cv2.COLOR_BGR2HSV)
	img_hsv[:,:,0] = _val
	img_BBB = cv2.cvtColor(img_hsv, cv2.COLOR_HSV2BGR)
	return np.dstack([img_BBB[:,:,:3], _img[:,:,3]])

######
## Tester
######
def testOutModes_wrap(main, mask, msg = "<< Using Wrapper >>", _opt=None): ## To use [testOutModes] in ad-hoc way
	show = True
	opt = _opt if _opt is not None else makeOptions(locals())
	_main = converterScaled(opt, main, None, True)
	_mask = converterScaled(opt, mask, None, True)
	testOutModes(opt, _main, _mask, 256, msg, advanced=True)

"""
#### https://pythonhosted.org/blend_modes/
#### %appdata%\..\Local\Programs\Python\Python38-32\Lib\site-packages\blend_modes
a = base \\ b = top layer \\ ai,bi = inverted

BW image == homogenous grayscale
_ab := If one is BW and other not, the non BW one
_AB := If one is BW and other not, the BW one

Normal        ([01] bm.normal)			== b // == alpha(b,a)
#// Multiply and Screen
Multiply      ([08] bm.multiply)		== a * b
>	if either is BW, equivalent to normal("black", _ab, alpha=_AB)
Screen        ([04] bm.screen)			== 1 - ai * bi
>	if either is BW, equivalent to normal(_ab, "white", alpha=_AB)
Overlay       ([15] bm.overlay)			== (a < 0.5) ? 2 a b : 1 - 2 ai bi
>	B << A => Lighten, B >> A -> Darken
>	Linear interpolation between black \\ [B] \\ white (at a=0, 0.5, 1)
Hard Light    ([09] bm.hard_light)		== overlay(b, a, alpha)
Soft Light    ([02] bm.soft_light)		== IMG_RGB_iv * multiply + IMG_RGB * screen
>	Softer version (more base bleeding)
#// Dodge and Burn
Dodge         ([05] bm.dodge)			== np.min(IMG_RGB / TAR_RGB_iv, 1)
Burn          							== Dodge of negative; darkens
#// Simple arithmetic
Divide        ([14] bm.divide)			== (256 / 255 * IMG_RGB) / (1 / 255 + TAR_RGB)
Addition      ([06] bm.addition)		== IMG_RGB + TAR_RGB
Subtract      ([11] bm.subtract)		== IMG_RGB - TAR_RGB
Difference    ([10] bm.difference)		== IMG_RGB - TAR_RGB; OUT[OUT < 0] *= -1
>	No change with black, inverted with White
Darken Only   ([07] bm.darken_only)		== np.min(IMG_RGB, TAR_RGB)
Lighten Only  ([03] bm.lighten_only)	== np.max(IMG_RGB, TAR_RGB)
#// Other
Grain Extract ([12] bm.grain_extract, GIMP) == np.clip(IMG_RGB - TAR_RGB + 0.5, 0, 1)
Grain Merge   ([13] bm.grain_merge, GIMP)   == np.clip(IMG_RGB + TAR_RGB + 0.5, 0, 1)
"""
def testOutModes(opt, _imgA, _imgB, size=256, msg="", advanced=False, _alpha=None):
	if not opt["show"]: return
	print("ColorTest: " + msg)
	alpha = opt["alpha"] if _alpha is None else _alpha
	scale = opt["scale"]
	imgA = _imgA.astype(float)
	imgB = _imgB.astype(float)
	if (imgA.shape[0] > 512) or (imgB.shape[0] > 512):
		imgA = resizeWithAspectRatio(imgA, width=512)
		imgB = resizeWithAspectRatio(imgB, width=512)
	
	img_seg = blend_modes.normal(imgA, imgB, alpha) * scale
	DisplayWithAspectRatio(opt, '[Nor]', img_seg, size) ### Alpha only
	img_seg = blend_modes.overlay(imgA, imgB, alpha) * scale
	DisplayWithAspectRatio(opt, '[Ovl]', img_seg, size) ### Alpha only
	img_seg = blend_modes.multiply(imgA, imgB, alpha) * scale
	DisplayWithAspectRatio(opt, '[Mul]', img_seg, size) ### Alpha only
	img_seg = blend_modes.difference(imgA, imgB, alpha) * scale
	DisplayWithAspectRatio(opt, '[Diff]', img_seg, size) ### Inverted + alpha: Alpha
	if advanced:
		img_seg = blend_modes.addition(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[Add]', img_seg, size) ## Inverted color without Alpha
		img_seg = blend_modes.subtract(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[Sub]', img_seg, size) ## Scambled, without Alpha
		img_seg = blend_modes.soft_light(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[Soft Light]', img_seg, size) ### Alpha only
		img_seg = blend_modes.lighten_only(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[Lighten]', img_seg, size) ### Increase LUM of A by alpha*B
		img_seg = blend_modes.darken_only(imgA, imgB, alpha) * scale ### Normal + alpha; Better [White] than inv+Difference
		DisplayWithAspectRatio(opt, '[Darken]', img_seg, size)
		img_seg = blend_modes.hard_light(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[Hard_Light]', img_seg, size) ### Alpha only
		img_seg = blend_modes.dodge(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[Dodge]', img_seg, size) ### No effect
		img_seg = blend_modes.screen(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[Screen]', img_seg, size) ### == Add
		img_seg = blend_modes.divide(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[Div]', img_seg, size) ### Scambled
		img_seg = blend_modes.grain_extract(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[GExtract]', img_seg, size) ### Scambled
		img_seg = blend_modes.grain_merge(imgA, imgB, alpha) * scale
		DisplayWithAspectRatio(opt, '[GMerge]', img_seg, size) ### Alpha only
	k = cv2.waitKey(0) & 0xFF

