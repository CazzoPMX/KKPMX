# Cazoo - 2021-05-13
# This code is free to use, but I cannot be held responsible for damages that it may or may not cause.
#####################
### sys
import json
import os
import re
import copy
from typing import List, Tuple

### Library -- Don't import any KKPMX files to avoid recursion
import nuthouse01_core as core
#import nuthouse01_pmx_parser as pmxlib
#import nuthouse01_pmx_struct as pmxstruct
import morph_scale
### 

## Global Debug Flag
DEBUG=False

## Global Debug Flag for debugging Script-Files only
FILEDEBUG=False
PRODUCTIONFLAG=True
## 
global_state = { }
HAS_UNITY = "UNITY"
OPT_WORKDIR = "WORKINGDIR"
OPT_AUTO = "automatic"
ALL_YES = "all_yes"
OPT_INFO = "moreinfo"

VERSION_DATE = "2024-03-05"
VERSION_TAG = "2.4.1"

def main_starter(callback, message="Please enter name of PMX input file"):
	"""
	Quickstarter for running from console
	if 'callback' is null, returns a tuple of (pmx, input_filename_pmx)
	Otherwise supplies these as arguments for callback
	
	## Template
	def run(pmx, input_filename_pmx): pass
	if __name__ == '__main__': util.main_starter(run)
	"""
	import nuthouse01_pmx_parser as pmxlib
	# prompt PMX name
	core.MY_PRINT_FUNC(message + ":")
	input_filename_pmx = core.MY_FILEPROMPT_FUNC(".pmx").strip('"')
	pmx = pmxlib.read_pmx(input_filename_pmx, moreinfo=True)
	if callback == None: return (pmx, input_filename_pmx)
	core.MY_PRINT_FUNC("====---====")
	callback(pmx, input_filename_pmx)
	core.MY_PRINT_FUNC("====---====")
	core.MY_PRINT_FUNC("Done!")

######
## JSON
######

def load_json_file(path=None, extra=None):
	"""
	Ask for a *.json file, adjust formatting for python, and return parsed result.
	Removes Comments & trailing commas; Fixes invalid escapes
	
	@parem path  [str] The path to load from. Prompts if missing.
	@param extra [(str) -> str] Perform extra processing on raw json string; Optional
	
	@returns [dict] parsed JSON object
	@returns [None] in case of errors
	"""
	def fix_JSON(json_message=None): ## https://stackoverflow.com/a/37805536
		work_msg = json_message
		while True:
			result = fix_JSON_loop(work_msg)
			if result[0]:
				#write_json(work_msg, "C:\koikatsu_model\TestTest")
				return result[1]
			if result[1] is None: return None
			work_msg = result[1]
	def fix_JSON_loop(json_message=None): ## https://stackoverflow.com/a/37805536
		result = None
		try:
			result = json.loads(json_message)
		except Exception as e:
			# Only continue on invalid escapes
			if str(e).find("Invalid \escape") == -1:
				print(e)
				return (False, None)
			#print(e)
			# Find the offending character index:
			idx_to_replace = int(str(e).split(' ')[-1].replace(')', ''))
			
			# Remove the offending character:
			json_message = list(json_message)
			json_message[idx_to_replace] = ''
			new_message = ''.join(json_message)
			return (False, new_message)
		return (True, result)
	## Validate path
	if path and (not os.path.exists(path)):
		print(f">> Requested file '{path}' does not exist!")
		path = None
	if (not path):
		print("----")
		path = core.MY_FILEPROMPT_FUNC("json")
		print("----")
	else: print("-- Parsing " + path)
	### Read file
	try:
		with open(path, 'r', encoding='utf-8') as myfile: raw_data = myfile.read()
	except Exception as e:
		print(e)
		return None
	### Parse JSON
	if extra: raw_data = extra(raw_data)
	def replFnc(m):
		for x in range(1,3):
			if m.group(x): return m.group(x)
	raw_data = re.sub(r'("(?:\\"|[^"])+")|//.+',     r'\1',   raw_data) ### remove Comments
	raw_data = re.sub(r'("(?:\\"|[^"])+")|,(\s*\})', replFnc, raw_data) ### remove trailing commas in objects
	raw_data = re.sub(r'("(?:\\"|[^"])+")|,(\s*\])', replFnc, raw_data) ### remove trailing commas in lists
	raw_data = raw_data.rstrip(',')
	data = fix_JSON(raw_data)
	if data == None:
		print("Encountered non escape error. Terminating")
		return None
	return data

def write_jsonX(data, path, **kwargs):
	""" Wraps 'with open(path, "w").write(...)' for json.dumps """
	with open(path, "w") as f: f.write(json.dumps(data, **kwargs))

def write_json(data, path, indent=True):
	""" Shorthand for writing a JSON file; Adds '.json' if missing """
	if not path.endswith(".json"): path += ".json"
	_indent = "\t" if indent else None
	with open(path, "w") as f:
		f.write(json.dumps(data, indent=_indent))

def parse_Tuple(data, _def):
	return _def if (re.match(r"\([\d,\.\- ]+\)", data) is None) else eval(data)

def read_file(data, path):
	return open(path, mode='r', encoding='utf-8').read()
	
def write_file_append(data, path):
	with open(path, "a", encoding='utf-8') as f: f.write(data)

######
## Generic
######

def sort_dict(_dict, deep=True, _type=None):
	"""
	Sort the keys of a dictionary with [sorted()]
	
	@param deep [bool] Sorts by using [sort_keys] of the json module. Default true
	@param _type [build-in] Cast all keys to [_type] before sorting
	
	@return a copy of [_dict] with keys sorted accordingly.
	"""
	if deep: return json.loads(json.dumps(_dict, sort_keys=True))
	tmp = {}
	if _type is None:
		for i in sorted(_dict): tmp[i] = _dict[i]
		return tmp
	for i in sorted(_dict.items(), key=lambda kv: _type(kv[0])):
		tmp[i[0]] = i[1]
	return tmp

def ask_yes_no(message, default=None, extra=None, check=None):
	"""
	return check if not None
	print extra if not None
	if default is None: return "{input} [y/n]?" == 'y'
	if default is  'y': if input is empty: return True
	any other default : if input is empty: return False
	"""
	if check is not None: return check
	if extra is not None: print("\n> [" + extra + "]")
	if default is None: return core.MY_GENERAL_INPUT_FUNC(lambda x: x in ['y','n'], message + " [y/n]?") == 'y'
	txt = "[y]/n" if default == "y" else "y/[n]"
	value = core.MY_GENERAL_INPUT_FUNC(lambda x: x in ['y','n',None,""], message + f" ({txt})?")
	if value in [None,""]: return default == "y"
	return value == "y"

def ask_direction(message, allow_empty=False):
	def is_valid(x):
		if allow_empty and x in [None,""]: return True
		if not x.isdigit(): return False
		return int(x) in [0,1,2,3,4,5]
	#print("0/1=X+ X-, 2/3=Y+ Y-. 4/5=Z+ Z- (left/right, up/down, back/front)")
	print("0/1=X- X+, 2/3=Y- Y+. 4/5=Z- Z+ (right/left, down/up, front/back)")
	msg = "0/1/2/3/4/5 or nothing" if allow_empty else "0/1/2/3/4/5"
	val = core.MY_GENERAL_INPUT_FUNC(is_valid, message + f"? [{msg}]: ")
	if allow_empty and val in [None, ""]: return None
	return int(val)

def ask_choices(message: str, choices: List[Tuple[str, object]], check=None):
	"""
	message: str    -- Displayed at the start
	choices: List of (str, object) -- The choices to list as "idx: KEY", with choices[idx] = VALUE
	check:   object -- Optional provide a value to use immediately without asking.
	"""
	if check in [x[1] for x in choices]: return check
	print("-- " + message + ":")
	idx = core.MY_SIMPLECHOICE_FUNC(range(len(choices)), [(str(i)+": "+str(choices[i][0])) for i in range(len(choices))])
	return choices[idx][1]

def ask_number(message: str, min_val=None, max_val=None, default=None):
	if DEBUG and min_val is not None and max_val is not None:
		if type(min_val) != type(max_val): raise Exception("Numbers are not same type!")
	
	def is_valid(x):
		if not is_number(x): return False
		return is_in_range(float(x), min_val, max_val)
	if not is_number(default):
		val = core.MY_GENERAL_INPUT_FUNC(is_valid, f"{message} [{min_val}..{max_val}]: ")
	else:
		msg = f"{message} [{min_val}..{max_val}](Default: {default}): "
		val = core.MY_GENERAL_INPUT_FUNC(lambda x: x in [None,""] or is_valid(x), msg)
		if val in [None, ""]: return default
	return float(val)
## if asking for list of numbers as "x,x" or "[x,x]" or "[[x,x],[x,x]]", check rigging

def ask_array():
	all_arr=[]
	def is_valid_bulk(value):
		if is_valid(value): return True
		if is_csv_number(value): return len(value.split(',')) == 2
		return is_csv_array(value)
	def is_valid(value): return is_number(value) and int(value) > -1 and int(value) < len(pmx.bones)
	def looper(start, end, log=True, all_arr=[]):
		if start < end:
			arr = list(range(int(start), int(end)+1))
			all_arr += arr
			#if log: arr_log.append("> " + json.dumps(arr))
			#patch_bone_array(pmx, None, arr, pmx.bones[arr[0]].name_jp, 16, False)
		else: print("> End must be bigger than start")
	start = core.MY_GENERAL_INPUT_FUNC(is_valid_bulk, "First Bone (or Pair or JSON-Array)" + f"?: ")
	if is_number(start): looper(start, core.MY_GENERAL_INPUT_FUNC(is_valid, "Last Bone"  + f"?: "), True, all_arr)
	else:
		if not start.startswith('[['):
			if "-" in start: start = re.sub("-", ",", start)
			if not start.startswith('['): start = f"[[{start}]]" ## Wrap flat pairs
			else: start = f"[{start}]" ## Wrap lists without enclosing bracket
		#arr_log.append(">>> " + json.dumps(json.loads(start)))
		for x in json.loads(start):
			if len(x) < 2: continue
			if len(x) == 2: looper(x[0], x[1], False, all_arr)
			else:
				all_arr += x
				#patch_bone_array(pmx, None, x, pmx.bones[x[0]].name_jp, 16, False)
		#print("> Done")
	return all_arr


def now(epoch=False): ## :: str(dt) == dt.isoformat(' ')
	"""
	Returns the current time as ISO Timestamp
	
	:param [epoch] True to return a numeric unix timestamp instead
	"""
	from datetime import datetime, timezone
	if epoch: # https://stackoverflow.com/questions/16755394
		return datetime.now(tz=timezone.utc).timestamp()
	return datetime.now().isoformat()

def copy_file(src, dst): # https://stackoverflow.com/questions/123198
	from shutil import copyfile, copy2
	#copyfile(src, dst)
	if src == dst: return
	try:    copy2(src, dst)
	except:
		if not os.path.exists(src):
			print(f"[!!] <FileNotFound> Failed to copy '{src}' to '{dst}'")
		else: print(f"[!!] Failed to copy '{src}' to '{dst}'")

#def makeDebugPrinter(condition):
#	if DEBUG or condition: return lambda x: print(x)
#	return lambda x: pass
def throwIfDebug(isDebug, text):
	if isDebug: raise Exception(text)
	print(f"[W]: {text}")

###############
### Globals ###
###############

def is_univrm(): return global_state.get(HAS_UNITY, False)
def set_globals(base_file):
	global_state[OPT_WORKDIR] = ""
	if not base_file: return
	path = os.path.split(base_file)[0]
	global_state[OPT_WORKDIR] = path
	path = os.path.join(path, "UNITY_MARKER");
	if (os.path.exists(path)): global_state[HAS_UNITY] = True
def is_allYes(): return global_state.get(ALL_YES, False)
def is_auto(): return global_state.get(OPT_AUTO, False)
def is_prod(): return PRODUCTIONFLAG
def is_verbose(): return global_state.get(OPT_INFO, False)

################
### Numerics ###
################

def is_number(text, allow_bool=False):
	if type(text) is bool: return allow_bool
	try:
		return float(text) is not None
	except:
		return False

# Checks if [text] has the form 000,000,000,000 (ignoring spaces)
def is_csv_number(text): return all([is_number(x.strip()) for x in text.split(',')])
def is_csv_array(text, allow_float=False):
	arr = None
	try:
		arr = json.dumps(json.loads(text))
	except Exception as e:
		print(e)
		return False
	if allow_float: return re.search("^[\[\]\d,\. ]+$", arr)
	return re.search("^[\[\]\d, ]+$", arr)

def is_valid_index(val, arr): return is_number(val) and val >= 0 and val < len(arr)
def is_in_range(val, min_val=None, max_val=None): return limit_to_range(val, min_val, max_val) == val
def limit_to_range(val, min_val=None, max_val=None):
	if val is None: return None
	#if not is_number(min_val): min_val=None
	#if not is_number(max_val): max_val=None
	if max_val is None:
		if min_val is None: return val
		return max(min_val, val)
	elif min_val is None: return min(max_val, val)
	return min(max(min_val, val), max_val)

def get_list_of_numbers(num, lim, msg):
	if not is_number(num):
		print("num is not a number"); return []
	num = int(num)
	if num < 1: return []
	arr = []
	print(msg)
	while(True):
		value = core.MY_GENERAL_INPUT_FUNC(is_csv_number, f"> Input a list of {num} numbers, separated by ',' (example: 1,2,3)")
		arr = [int(x.strip()) for x in value.split(',')]
		if len([True for i in arr if lim[0] > i or i > lim[1]]) == 0: break
		print(f"Invalid values (allowed are {lim[0]} - {lim[1]})")
	while(len(arr) < num): arr.push(0)
	return arr[:num]

def get_span_within_range(_arrLen, _min, _max):
	ret = [0, _arrLen-1]
	## Check min: Too small = 0 \\ too big = len
	#== 0 <= _min <= len
	ret[0] = min(max(ret[0], _min), ret[1])
	## Check max: Too big = max \\ Below min: use min
	#== _min <= _max <= len
	ret[1] = min(max(ret[0], _max), ret[1])
	return tuple(ret)

def flatten(arr): return [a for ar in arr for a in ar]
def normalize(arr, val): return [a % val for a in arr]
def chunk(lst, n): return [lst[i:i + n] for i in range(0, len(lst), n)]
def pairwise(lst): return zip(*[iter(lst)]*2)
def arrSub(x, y): return (Vector3.FromList(x) - (Vector3.FromList(y))).ToList()
def arrMul(x, y): return (Vector3.__rmul__(Vector3.FromList(x), scale=y)).ToList()
def arrAvg(x, y, asInt=False):
	vX = Vector3.FromList(x); vY = Vector3.FromList(y)
	arr = (Vector3.__rmul__(vX + vY, 0.5)).ToList()
	if asInt: arr = [int(arr[0]), int(arr[1]), int(arr[2])]
	return arr
def arrInvert(x): return (-(Vector3.FromList(x))).ToList()
def arrCmp(x, y): return Vector3.FromList(x) == Vector3.FromList(y)

def addOrExt(d,key,val):
	arr = d.getdefault(key,[])
	arr.append(val)
	d[key] = arr

def unify_names(arr):
	names = []
	for a in arr:
		name = a.name_jp; idx = 0
		while name in names:
			idx = idx+1
			name = a.name_jp + f"*{idx}"
		a.name_jp = name
		names.append(name)

class DictAppend(dict):
	def __init__(self, initVal: int):
		self.initVal = initVal
	def addOrInit(self, key, default, func):
		self[key] = func(self.getdefault(key, default))
	#__getitem__: https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence
	def __missing__(self, key): ## Called by dict[key] if key is not in the mapü
		#self.__setitem__
		return self.initVal


#############
### Texts ###
#############

import unicodedata
import re

# https://stackoverflow.com/a/295466
def slugify(value, allow_unicode=False):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')

def contains(src, what, ignore=True): return re.search(what, src, re.I if ignore else 0) is not None

##-- Convert a list into a Regex-Pattern
def matchList(arr, isFix=False):
	if not arr or len(arr) == 0: raise Exception("Not allowed with empty")
	if isFix: re.compile(r'\b(' + r'|'.join(arr) + r')\b', flags=re.I)
	return re.compile(r'|'.join(arr), flags=re.I)

##-- Translate a name if it needs to be translated, and return accordingly
def translate_name(name_jp, name_en):
	import _translation_tools as tlTools
	if not(name_en is None or name_en == ""):   return name_en
	if not tlTools.needs_translate(name_jp):    return name_jp
	return tlTools.local_translate(name_jp)

def make_printer(flag):
	if flag: return lambda text: print(text)
	return lambda text: 1+1

def is_ascii(s):
	try:
		s.encode('ascii'); return True
	except UnicodeEncodeError:
		return False

matsRgx = re.compile(r"( \(Instance\))*(@\w+|#\-\d+)")
fileRgx = re.compile(r"[<>:\"/\\|?*]")
def get_unique_name(init: str, tabu: list, isFile = False) -> str:
	"""
	Uniquefy a name based on a list of provided names.
	Adds the element to [names] before returning.
	
	:param init: desired file path, absolute or relative
	:param tabu: list/set of forbidden names
	:param isFile: optional flag to handle init as FileName
	:return: init with integers appended until it becomes unique (if needed)
	"""
	name = init
	pattern = "{}*{}"
	if isFile:
		import os
		base, init = os.path.split(init)
		init       = fileRgx.sub("", init)     ## Cut off dir path to only clean file name
		name, ext  = os.path.splitext(init)    ## ... and to make sure we take the actual extension
		init       = os.path.join(base, init)  ## then glue together again
		pattern    = base + "/{}_{}" + ext
	else: init = matsRgx.sub("", init)
	
	if init in tabu:
		suffix = 0
		while True:
			suffix += 1
			if (pattern.format(name, suffix)) not in tabu: break
		name = pattern.format(name, suffix)
	else: name = init
	tabu.append(name)
	return name

######
## Finders
######

find_info = """ [pmx] instance -- Entity Name -- Flag to print error if not found (default True) -- idx to start at (default 0)"""

def __find_in_pmxsublist(name, arr, e, idx):
	if not is_number(idx) or idx < 0: idx = 0
	if idx >= len(arr): return -1
	idx = int(idx)
	if idx > 0: arr = arr[idx : -1]
	result = morph_scale.get_idx_in_pmxsublist(name, arr, e)
	return -1 if result in [-1, None] else result + idx

def find_bone (pmx,name,e=True,idx=0): return __find_in_pmxsublist(name, pmx.bones,e,idx)
def find_mat  (pmx,name,e=True,idx=0): return __find_in_pmxsublist(name, pmx.materials,e,idx)
def find_disp (pmx,name,e=True,idx=0): return __find_in_pmxsublist(name, pmx.frames,e,idx)
def find_morph(pmx,name,e=True,idx=0): return __find_in_pmxsublist(name, pmx.morphs,e,idx)
def find_rigid(pmx,name,e=True,idx=0): return __find_in_pmxsublist(name, pmx.rigidbodies,e,idx)
def find_joint(pmx,name,e=True,idx=0): return __find_in_pmxsublist(name, pmx.joints,e,idx)
find_bone.__doc__ = find_mat.__doc__ = find_disp.__doc__ = find_morph.__doc__ = find_rigid.__doc__ = find_joint.__doc__ = find_info
### Technically could also be just -- core.my_list_search(arr, lambda x: (x.name_jp == "name_jp" ... ))
def find_all_in_sublist(name, arr, returnIdx=True):
	result = []
	idx = -1
	if not PRODUCTIONFLAG:
		if name in [None, ""]: raise Exception("Empty Name!")
	for item in arr:
		idx += 1
		_name = f"{item.name_jp};{item.name_en}"
		if not contains(_name, name): continue
		result.append(idx if returnIdx else item)
	return result

def find_bones(pmx, arr, flag=True, returnIdx=True):
	result = []
	for name in arr:
		idx = find_bone(pmx, name, flag)
		if returnIdx: result.append(idx)
		elif idx != -1: result.append(pmx.bones[idx])
		else: result.append(None)
	return result

######
## Common (4:Bones)
#####

def find_or_return_bone(pmx, nameOrIdx, errFlag=True):
	if type(nameOrIdx) == type(""):
		return find_bone(pmx, nameOrIdx, errFlag)
	return nameOrIdx
find_or_return_bone.__doc__ = """ if [nameOrIdx] is a string, return result of [find_bone], otherwise return directly. """

def rename_bone(pmx, org, newJP, newEN):
	tmp = find_bone(pmx, org, False)
	if tmp != -1:
		if newJP is not None: pmx.bones[tmp].name_jp = newJP
		if newEN is not None: pmx.bones[tmp].name_en = newEN
	return tmp

def bind_bone(pmx, _arr, last_link=False): ##-- TODO_Test(again): [rigging]
	from copy import deepcopy
	arr = deepcopy(_arr)
	### Enclose in [] to make a bone optional
	test = [type(x) == type([]) for x in arr]
	if any(test):
		_arr = []
		for i,x in enumerate(arr):
			if not test[i]: _arr.append(x)
			elif find_or_return_bone(pmx, x[0], False) != -1: _arr.append(x[0])
		arr = _arr
	
	while len(arr) > 1:
		parent = find_or_return_bone(pmx, arr[0], False)
		child = find_or_return_bone(pmx, arr[1], False)
		#print(f"Linking {arr[0]:10}={parent:3} to {arr[1]:10}={child:3}")
		if parent != -1 and child != -1:
			pmx.bones[parent].tail_usebonelink = True
			pmx.bones[parent].tail = child
		arr.pop(0)
	if last_link:
		pmx.bones[arr[-1]].tail_usebonelink = False
		pmx.bones[arr[-1]].tail = [0, 0, -0.1]

def set_parent_if_found(pmx, childName, parent, is_rigid=False):
	parent = find_or_return_bone(pmx, parent)
	if parent == -1: return
	if is_rigid:
		idx = find_rigid(pmx, childName, False)
		if idx == -1: return
		pmx.rigidbodies[idx].bone_idx = parent
	else:
		idx = find_bone(pmx, childName, False)
		if idx == -1: return
		pmx.bones[idx].parent_idx = parent

def replace_with_parent(pmx, boneName):
	boneIdx = find_or_return_bone(pmx, boneName)
	if boneIdx == -1: return
	bone = pmx.bones[boneIdx]
	grandparent = pmx.bones[bone.parent_idx].parent_idx
	bone.parent_idx = grandparent
#:in [core]
#	Find all bones starting with NAME and return all their children as indices
#	Return all indices of the children of NAME
#:in [rigging]
#	get_parent_map
#	get_children_map

######
## Common (3:Materials)
#####

def updateComment(_comment:str, _token, _value=None, _replace=False, _append=False):
	"""
	Wraps [_token] into f"[:{_token}:]", then calls updateCommentRaw
	"""
	return updateCommentRaw(_comment, f"[:{_token}:]", _value, _replace, _append)
#def updateCommentRaw(_comment:str, _token, _value=None, _replace=False, _append=False):
#	return _updateCommentRaw(_comment, f"[:{_token}:]", _value, _replace, _append)
def updateCommentRaw(_comment:str, _token, _value=None, _replace=False, _append=False):
	"""
	_token will be regex escaped before search; _value is appended as-is (with ' ' inbetween)
	Returns the comment without a previous occurence of [_token] and the new one at the start
	:[_replace]: -- Update in-place if it exists instead of removing and prepending
	"""
	_str = f"{_token}" # ensures it is at least an empty string if None
	if _value is not None: _str += ' ' + str(_value)
	if not _comment: _comment = ""
	if len(_comment.strip()) == 0: return _str
	if _replace:
		if readFromCommentRaw(_comment, _token, exists=True):
			return re.sub(re.escape(_token) + r".*", f"{_str}", _comment)
	else: _comment = re.sub(r"(\r?\n)?" + re.escape(_token) + r".*", "", _comment)
	if _append: return "\r\n".join([_comment, _str])
	return "\r\n".join([_str, _comment])

def readFromComment(_comment:str, _term:str, exists:bool = False):    return _readFromCommentRaw(_comment, r'\[:' + f"{_term}" + r':\]', exists)
def readFromCommentRaw(_comment:str, _term:str, exists:bool = False): return _readFromCommentRaw(_comment, re.escape(_term), exists)
def _readFromCommentRaw(_comment:str, _term:str, exists:bool = False):
	try:
		if exists:
			return re.search(_term, _comment) is not None
		m = re.search(_term + r' *([^\r\n]+)', _comment)
		if not m: return None
		return m[1]
	except:
		print(f"[!] Error while searching '{_term}' in '{_comment}'")
		return None
def isDisabled(mat): return re.search(r'\[:Disabled?:\]', mat.comment) is not None


def find_all_mats_by_name(pmx, name, withName=False):
	result = []
	for mat in pmx.materials:
		_name = f"{mat.name_jp};{mat.name_en}"
		if not contains(_name, name): continue
		_comment = mat.comment
		if not _comment: _comment = ""
		m = re.search("\[:AccId:\] (\d+)", _comment)
		if not m: continue
		if withName:
			result.append([f"ca_slot{m[1]}", mat.name_jp])
		else: result.append(f"ca_slot{m[1]}")
	return result

def find_bodyname(pmx): return "cf_m_body" if find_mat(pmx, "cm_m_body", False) == -1 else "cm_m_body"
def find_bodypar(pmx): return "p_cf_body_00" if find_mat(pmx, "cm_m_body", False) == -1 else "p_cm_body_00"
def is_male(pmx): return find_bodyname(pmx) != "cf_m_body"

def is_bodyMat(mat):
	return re.search("ct_head", mat.comment) or \
		mat.name_jp in ["cf_m_face_00", "cf_m_body", "cm_m_body", "cf_m_mm"] or \
		mat.name_jp in ["cf_m_eyeline_kage", "cf_m_tooth", "cf_m_sirome"]

def is_primmat(mat): return mat.name_jp.startswith("mf_m_primmaterial")

def findMat_Face(pmx):
	idx = find_mat(pmx, "cf_m_face_00", True)
	if idx != -1: return idx
	for (idx,mat) in enumerate(pmx.materials):
		slot    = readFromComment(mat.comment, "Slot")
		MatType = readFromComment(mat.comment, "MatType")
		if (MatType == "Face"): return idx
		if (slot == "ct_head" and MatType == "Body"): return idx
	return -1

######
## Common (3b:Textures)
#####

def move_unused_to_folder(pmx, input_filename_pmx):
	from pathlib import Path
	from shutil import move
	source = os.path.dirname(input_filename_pmx)
	target = os.path.join(source, "unused")
	if not os.path.exists(target): os.mkdir(target)
	files = Path(source).glob('*.png')
	for oldname in files:
		basePath, name = os.path.split(oldname)
		newname = os.path.join(target, name)
		move(oldname, newname)

def move_unused_from_folder(pmx, input_filename_pmx):
	from pathlib import Path
	from shutil import move
	target = os.path.dirname(input_filename_pmx)
	source = os.path.join(target, "unused")
	if not os.path.exists(source): return
	files = Path(source).glob('*.png')
	for oldname in files:
		basePath, name = os.path.split(oldname)
		newname = os.path.join(target, name)
		move(oldname, newname)

######
## Common (6:Display)
#####

def add_to_facials(pmx, name):
	#pmx.frames.append(pmxstruct.PmxFrame(name_jp="moremorphs", name_en="moremorphs", is_special=False, items=newframelist))
	idx = find_disp(pmx, "表情", False)
	if idx != -1:
		target = name
		if type(target).__name__ == "str": target = find_morph(pmx, name, False)
		if target != -1: pmx.frames[idx].items += [[1, target]]


######
## Common (1:Vertices)
#####

#-- Split List of Vertices into Left and Right --> morphs.generateWink (by find_morph)

def process_vertex_weights(verts, searchFor, replaceWith):
	def replaceBone(target): return replaceWith if target == searchFor else target
	for vert in verts: process_weight(vert, replaceBone)
def process_weight_if_major(verts, main, removeIfFound):
	if type(verts) != type([]): verts = [verts]
	def replaceBone(target): return main if target == removeIfFound else target
	for vert in verts:
		if vert.weighttype == 1:
			if vert.weight[2] > 0.5: process_weight(vert, replaceBone)
		elif vert.weighttype == 2:
			if vert.weight[4] > 0.5: process_weight(vert, replaceBone)

def process_weight(vert, action):
	if vert.weighttype == 0:
		vert.weight[0] = action(vert.weight[0])
	elif vert.weighttype == 1:
		vert.weight[0] = action(vert.weight[0])
		vert.weight[1] = action(vert.weight[1])
	elif vert.weighttype == 2:
		vert.weight[0] = action(vert.weight[0])
		vert.weight[1] = action(vert.weight[1])
		vert.weight[2] = action(vert.weight[2])
		vert.weight[3] = action(vert.weight[3])

def get_weightIdx(vert):
	w = vert.weight
	if vert.weighttype == 0:   return [w[0]]
	elif vert.weighttype == 1: return w[0:1]
	elif vert.weighttype == 2: return w[0:3]
	raise Exception("....")
def get_weightVal(vert):
	w = vert.weight
	if vert.weighttype == 0:   return [1]
	elif vert.weighttype == 1: return [w[2], 1 - w[2]]
	elif vert.weighttype == 2: return w[4:]
	raise Exception("....")


def get_vertex_box(pmx, mat_idx, returnIdx=False):
	""" Return the bounding box of the given material """
	from kkpmx_core import from_material_get_faces, from_faces_get_vertices
	faces = from_material_get_faces(pmx, mat_idx, False, moreinfo=False)
	verts = from_faces_get_vertices(pmx, faces, False, moreinfo=False)
	verts.sort(key=lambda e: e.pos[0]); lefBonePos = verts[0].pos; rigBonePos = verts[-1].pos
	#print(f"Left: {lefBonePos}, Right: {rigBonePos}")
	verts.sort(key=lambda e: e.pos[1]); botBonePos = verts[0].pos; topBonePos = verts[-1].pos
	#print(f"Top: {topBonePos}, Bottom: {botBonePos}")
	verts.sort(key=lambda e: e.pos[2]); froBonePos = verts[0].pos; bacBonePos = verts[-1].pos #NegZ is front
	#print(f"Front: {froBonePos}, Back: {bacBonePos}")
	if returnIdx: verts = from_faces_get_vertices(pmx, faces, True, moreinfo=False)
	else: verts.sort(key=lambda e: -e.pos[1]);
	
	center = [
		(lefBonePos[0] + rigBonePos[0]) / 2,
		(topBonePos[1] + botBonePos[1]) / 2,
		(froBonePos[2] + botBonePos[2]) / 2
		]
	
	
	return (verts, {
			"Left": lefBonePos, "Right": rigBonePos, 
			"Top": topBonePos, "Bottom": botBonePos, "Up": topBonePos, "Down": botBonePos,
			"Front": froBonePos, "Back": bacBonePos,
			"Center": center
		})
	######
	pass #

######
## Constants
######
from enum import Enum
class MatTypes(Enum):
	ANY = "Any"       # Anything else
	BODY = "Body"     # Designated if Skin or in ct_head
	FACE = "Face"     # Designated if Skin or in ct_head
	HAIR = "Hair"     # GameObjects with KKHairComponent
	CLOTH = "Cloths"  # GameObjects with KKClothComponent
	ACCS = "Acc"      # GameObjects with KKAccComponent
	BODYACC = "BodyAcc" # Weighted directly to Body Armature (example: Navel-Piercing)

######
## Math Types for Rigging
######

# https://en.wikipedia.org/wiki/Fast_inverse_square_root
import math

class Vector3():
	def __init__(self, X: float, Y: float, Z: float):
		self.X = X
		self.Y = Y
		self.Z = Z
	@staticmethod
	def UnitX(): return Vector3(1.0, 0.0, 0.0)
	@staticmethod
	def UnitY(): return Vector3(0.0, 1.0, 0.0)
	@staticmethod
	def UnitZ(): return Vector3(0.0, 0.0, 1.0)
	@staticmethod
	def Zero(): return Vector3(0.0, 0.0, 0.0)
	@staticmethod
	def FromList(arr): return Vector3(arr[0], arr[1], arr[2])
	def ToList(self): return [self.X, self.Y, self.Z]
	@staticmethod
	def FromDegree(arr):
		import math
		X = arr[0] * (math.pi/180)
		Y = arr[1] * (math.pi/180)
		Z = arr[2] * (math.pi/180)
		return Vector3(X, Y, Z)
	def ToDegree(self):
		import math
		self.X = self.X * (180/math.pi)
		self.Y = self.Y * (180/math.pi)
		self.Z = self.Z * (180/math.pi)
		return self
	
	def Length(self):
		import math
		return math.sqrt(self.X*self.X + self.Y*self.Y + self.Z*self.Z)
	def Normalize(self): ## In-place, return self instead of void
		num: float = self.Length()
		#print("[>] Norm Len " +str(num))
		if (num != 0.0):
			num2: float = float(1.0 / num)
			self.X = float(self.X * num2);
			self.Y = float(self.Y * num2);
			self.Z = float(self.Z * num2);
		return self
	@staticmethod
	def Cross(left, right):
		result: Vector3 = Vector3.Zero()
		#print(f"Left: {left}, Right: {right}")
		z : float  = right.Z
		y : float  = left.Y
		z2: float  = left.Z
		y2: float  = right.Y
		result.X   = (y * z) - (y2 * z2)
		x : float  = right.X
		x2: float  = left.X
		result.Y   = (x * z2) - (x2 * z)
		result.Z   = (x2 * y2) - (x * y)
		return result
	@staticmethod
	def Dot(left, right): ## return float of Vector3 x Vector3
		return float(float(left.Y) * float(right.Y) + float(left.X) * float(right.X) + float(left.Z) * float(right.Z));
	
	@staticmethod
	def TransformNormal(normal, transformation): ## Vector3 x Matrix --> Vector3
		result: Vector3 = Vector3.Zero()
		y: float = normal.Y;
		x: float = normal.X;
		z: float = normal.Z;
		result.X = float(float(transformation.M11) * float(x) + float(transformation.M21) * float(y) + float(transformation.M31) * float(z));
		result.Y = float(float(transformation.M12) * float(x) + float(transformation.M22) * float(y) + float(transformation.M32) * float(z));
		result.Z = float(float(transformation.M13) * float(x) + float(transformation.M23) * float(y) + float(transformation.M33) * float(z));
		return result;
	
	@staticmethod
	def LerpS(x, y, s): return x + s * (y - x)
	
	###------ Operators
	
	def __add__(value, scale:float):
		#print(f"__add__ with {value} \\ {scale}")
		result = Vector3.Zero()
		result.X = float(left.X + scale);
		result.Y = float(left.Y + scale);
		result.Z = float(left.Z + scale);
		return result;
	__radd__ = __add__
	
	def __add__(left, right):
		#print(f"__add__ with {left} \\ {right}")
		result = Vector3.Zero()
		result.X = float(left.X + right.X);
		result.Y = float(left.Y + right.Y);
		result.Z = float(left.Z + right.Z);
		return result;

	def __sub__(left, right):
		result = Vector3.Zero()
		result.X = float(left.X - right.X);
		result.Y = float(left.Y - right.Y);
		result.Z = float(left.Z - right.Z);
		return result;
		
	def __mul__(value, scale: float):
		#print(f"__mul__ with {value} \\ {scale}")
		result = Vector3.Zero()
		result.X = float(value.X * scale);
		result.Y = float(value.Y * scale);
		result.Z = float(value.Z * scale);
		return result;
	__rmul__ = __mul__
		
	def __mul__(left, right): ## Modulate
		result = Vector3.Zero()
		result.X = float(left.X * right.X);
		result.Y = float(left.Y * right.Y);
		result.Z = float(left.Z * right.Z);
		return result;
	
	def __truediv__(left, right):
		result = Vector3.Zero()
		result.X = float(left.X / right.X);
		result.Y = float(left.Y / right.Y);
		result.Z = float(left.Z / right.Z);
		return result;
	
	def __neg__(value): ## Negate
		result: Vector3 = Vector3.Zero()
		result.X = 0.0 - value.X
		result.Y = 0.0 - value.Y
		result.Z = 0.0 - value.Z
		return result
	def __str__(self):
		text = ""
		text += f"[{self.X:12.8}, {self.Y:12.8}, {self.Z:12.8}]"
		return text

class Quaternion():
	def __init__(self, X: float, Y: float, Z: float, W: float):
		self.X = X
		self.Y = Y
		self.Z = Z
		self.W = W
	def __init__(self, src: Vector3, W: float):
		self.X = src.X
		self.Y = src.Y
		self.Z = src.Z
		self.W = W
	@staticmethod
	def Zero(): return Quaternion(0.0, 0.0, 0.0, 0.0)
	@staticmethod
	def FromList(arr): return Quaternion(arr[0], arr[1], arr[2], arr[3])
	def ToList(self): return [self.X, self.Y, self.Z, self.W]
	
	##------- SlimDX::SlimDX.Quaternion
	@staticmethod
	def Conjugate(quaternion): #--> new Quaternion
		result: Quaternion = Quaternion.Zero;
		result.X = 0.0 - quaternion.X;
		result.Y = 0.0 - quaternion.Y;
		result.Z = 0.0 - quaternion.Z;
		result.W = quaternion.W;
		return result;

	@staticmethod
	def RotationAxis(axis: Vector3, angle: float): ##--> new Quaternion
		result: Quaternion = Quaternion.Zero;
		axis = axis.Normalize(); #== Vector3.Normalize(ref axis, out axis);
		num: float = angle * 0.5;
		num2: double = num;
		num3: float = float(math.sin(num2));
		w: float = float(math.cos(num2));
		result.X = float(float(axis.X) * float(num3));
		result.Y = float(float(axis.Y) * float(num3));
		result.Z = float(float(axis.Z) * float(num3));
		result.W = w;
		return result;

	def __mul__(left, right): ## Modulate
		result: Quaternion = Quaternion.Zero()
		#(x,y,z,w) = left;
		#(x2,y2,z2,w2) = right;
		x = left.X;		y = left.Y;		z = left.Z;		w = left.W;
		x2 = right.X;		y2 = right.Y;		z2 = right.Z;		w2 = right.W;
		result.X = float(float(x2) * float(w) + float(w2) * float(x) + float(y2) * float(z) - float(z2) * float(y));
		result.Y = float(float(y2) * float(w) + float(w2) * float(y) + float(z2) * float(x) - float(x2) * float(z));
		result.Z = float(float(z2) * float(w) + float(w2) * float(z) + float(x2) * float(y) - float(y2) * float(x));
		result.W = float(float(w2) * float(w) - (float(y2) * float(y) + float(x2) * float(x) + float(z2) * float(z)));
		return result;
	
	##------- PEPlugin::PEPlugin.SDX.Q
	@staticmethod
	def Dir(dstFront, dstUp, srcFront, srcUp):
		q: Quaternion = Quaternion.Zero
		return q.FromDirection(dstFront, dstUp, srcFront, srcUp)

	def FromDirection(self, dstFront: Vector3, dstUp: Vector3, srcFront: Vector3, srcUp: Vector3):
		srcFront = srcFront.Normalize();
		dstFront = dstFront.Normalize();
		srcUp = srcUp.Normalize();
		dstUp = dstUp.Normalize();
		axis: Vector3 = Vector3.Cross(srcFront, dstFront);
		num: float = Vector3.Dot(srcFront, dstFront);
		num = ((-1.0) if (num < -1.0) else num);
		num = (1.0 if (num > 1.0) else num);
		angle: float = float(math.acos(num));
		quaternion: Quaternion = Quaternion.RotationAxis(axis, angle);
		quaternion2: Quaternion = Quaternion.Conjugate(quaternion);
		quaternion3: Quaternion = Quaternion(srcUp, 0.0);
		quaternion4: Quaternion = quaternion2 * quaternion3 * quaternion;
		left: Vector3 = Vector3(quaternion4.X, quaternion4.Y, quaternion4.Z);
		left = left.Normalize();
		right: Vector3 = Vector3.Cross(dstUp, dstFront);
		right = right.Normalize();
		dstUp = Vector3.Cross(dstFront, right);
		dstUp = dstUp.Normalize();
		right2: Vector3 = Vector3.Cross(left, dstFront);
		right2 = right2.Normalize();
		left = Vector3.Cross(dstFront, right2);
		left = left.Normalize();
		num = Vector3.Dot(left, dstUp);
		num = ((-1.0) if (num < -1.0) else num);
		num = (1.0 if (num > 1.0) else num);
		angle = float(math.acos(num));
		## Org: this.m_q is Storage for SDX Wrapper
		m_q = None
		if (angle < 1E-05): m_q = quaternion
		else: m_q = quaternion * Quaternion.RotationAxis(Vector3.Cross(left, dstUp), angle);
		## Edit: return m_q instead of implicit cast
		return m_q

class Matrix():
	def __init__(self):
		self.M11 = 0.0
		self.M12 = 0.0
		self.M13 = 0.0
		self.M14 = 0.0
		self.M21 = 0.0
		self.M22 = 0.0
		self.M23 = 0.0
		self.M24 = 0.0
		self.M31 = 0.0
		self.M32 = 0.0
		self.M33 = 0.0
		self.M34 = 0.0
		self.M41 = 0.0
		self.M42 = 0.0
		self.M43 = 0.0
		self.M44 = 0.0

	@staticmethod
	def Identity():
		result = Matrix();
		result.M11 = 1.0;
		result.M22 = 1.0;
		result.M33 = 1.0;
		result.M44 = 1.0;
		return result;
	def __str__(self):
		text = "["
		text += f"[M11:{self.M11:14.10} M12:{self.M12:14.10} M13:{self.M13:14.10} M14:{self.M14:14.10}]\r\n"
		text += f"[M21:{self.M21:14.10} M22:{self.M22:14.10} M23:{self.M23:14.10} M24:{self.M24:14.10}]\r\n"
		text += f"[M31:{self.M31:14.10} M32:{self.M32:14.10} M33:{self.M33:14.10} M34:{self.M34:14.10}]\r\n"
		text += f"[M41:{self.M41:14.10} M42:{self.M42:14.10} M43:{self.M43:14.10} M44:{self.M44:14.10}]"
		return text + "]"
	@staticmethod
	def RotationQuaternion(rotation: Quaternion): # SimDX.Matrix
		result: Matrix = Matrix();
		x: float = rotation.X;
		num: double = x;
		num2: float = float(num * num);
		y: float = rotation.Y;
		num3: double = y;
		num4: float = float(num3 * num3);
		z: float = rotation.Z;
		num5: double = z;
		num6: float = float(num5 * num5);
		num7: float = float(float(y) * float(x));
		w: float = rotation.W;
		num8: float = float(float(w) * float(z));
		num9: float = float(float(z) * float(x));
		num10: float = float(float(w) * float(y));
		num11: float = float(float(z) * float(y));
		num12: float = float(float(w) * float(x));
		result.M11 = float(1.0 - (float(num6) + float(num4)) * 2.0);
		result.M12 = float((float(num8) + float(num7)) * 2.0);
		result.M13 = float((float(num9) - float(num10)) * 2.0);
		result.M14 = 0.0;
		result.M21 = float((float(num7) - float(num8)) * 2.0);
		result.M22 = float(1.0 - (float(num6) + float(num2)) * 2.0);
		result.M23 = float((float(num12) + float(num11)) * 2.0);
		result.M24 = 0.0;
		result.M31 = float((float(num10) + float(num9)) * 2.0);
		result.M32 = float((float(num11) - float(num12)) * 2.0);
		result.M33 = float(1.0 - (float(num4) + float(num2)) * 2.0);
		result.M34 = 0.0;
		result.M41 = 0.0;
		result.M42 = 0.0;
		result.M43 = 0.0;
		result.M44 = 1.0;
		return result;


######
## DataPrinter
######

def __dataPrinter_List(arr):
	print(":Len="+str(len(arr)))
	def __Printer(elem, idx=0, indent="- ", lvl=0):
		if type(elem) in [list, tuple]:
			print("{}[{}]: {} as {}".format(indent*lvl, idx, len(elem), type(elem).__name__))
			for (j,item) in enumerate(elem): __Printer(item,j,indent,lvl+1)
		else: print("{}[{}]: {}".format(indent*lvl, idx, elem))
	for idx,elem in enumerate(arr): __Printer(elem, idx)

######
## TypePrinter
######

def __typePrinter_test():
	print("====== Running TypePrinter Test ======")
	a = [1,2,3]; b = ['a','b','c']; d = {1:1, 2:2}
	def func(x): return x ### <**,...> := no __getitem__ \\ readonly := no set func (or etc) \\ iter := can only be iterated
	__typePrinter(123,          test="int")            # 
	__typePrinter(0e0,          test="float")          # 
	__typePrinter(10j,          test="complex")        # 
	__typePrinter(True,         test="bool")           # 
	__typePrinter("123",        test="str")            # ==               <int, string>
	__typePrinter(b'123',       test="bytes")          # == readonly      <int, int>
	__typePrinter(bytearray(a), test="bytearray")      # ==               <int, int>
	__typePrinter([1,2,3],      name="list")           # ==               <int, T>
	__typePrinter((1,2,3),      name="tuple")          # == readonly      <int, T>
	__typePrinter({1:1,2:2},    name="dict")           # ==               <K, V>		__getitem__, __hash__, __iter__, __len__, __setitem__
	__typePrinter(set(a),       name="set")            # ==          iter <**, T>		__hash__, __iter__, __len__
	__typePrinter(frozenset(a), name="frozenset")      # == readonly iter <**, T>		__hash__, __iter__, __len__
	__typePrinter(slice(0,5),   name="slice")          # == ??? \\ no __hash__ <<< {...}[:5] --> unhashable type 'slice'
	##### Special Types
	__typePrinter(list,         test="Type")
	__typePrinter(None,         test="None")
	__typePrinter(Ellipsis,     test="Ellipsis")
	__typePrinter(NotImplemented,  test="NotImplemented")
	### object(), property(), open()
	#print(":: Test Func::")      # == function          --> def, lambda, build-in \\ listcomp, dictcomp
	#__typePrinter(func)
	#__typePrinter(lambda x: x)
	#__typePrinter(len)
	#__typePrinter(a.append)
	#__typePrinter([].append) #== 'method', defines __func__ & __self__
	#import re \\ __typePrinter(re) #== 'module', defines __dict__
	print("------")
	#### build-in 
	print(":: Test build-in::")
	#>> Special iterable types
	__typePrinter(range(0,2))       # ==               <int, int>		__getitem__, __hash__, __iter__, __len__
	__typePrinter(map(func,b))      # ==          iter <**, T>			             __hash__, __iter__, __next__
	__typePrinter(filter(func,b))   # ==          iter <**, T>			             __hash__, __iter__, __next__
	__typePrinter(iter(a)           ,enum="List.Iter")          # == readonly iter <T>				             __hash__, __iter__, __next__, __length_hint__
	__typePrinter(zip(a,b))         # == ... \\ no __getitem__			             __hash__, __iter__, __next__
	print("== Test dictionary ==")
	#>> <view object>: live update for changes, support __len__, __getitem__, __iter__, __reversed__, *.mapping
	__typePrinter(d.keys()          ,enum="Dict.Keys")        # == <view object> --  + <set> because unique & hashable
	__typePrinter(d.values()        ,enum="Dict.Vals")        # == <view object> -- values on their own are never checked to be <set>-like
	__typePrinter(d.items()         ,enum="Dict.Items")       # == <view object> -- can be <set> if all values are hashable such that (k,v) is unique
	__typePrinter(iter(d.keys())    ,enum="Iter.Dict.Keys")   # == readonly iter <T>
	__typePrinter(iter(d.values())  ,enum="Iter.Dict.Vals")   # == readonly iter <T>
	__typePrinter(iter(d.items())   ,enum="Iter.Dict.Items")  # == readonly iter <T>
	#>> list_iterator, dict_keyiterator, dict_keys([<<contents>>])
	#---
	#### re.compile("") --> <re.Pattern object .... >
	#### re.match("")   --> <re.Match object; span=({res.span}), match='{res.group(0)}>
	#### compile(....)  --> ??? #== defines __code__ \\ can be used with exec() or eval()
	#### class XXX      --> <class 'module.XXX'> ++ __name__ == 'XXX'
	#### os.listdir(...) --> <class 'list'> of <class 'str'>
	#### os.scandir(...) --> <class 'nt.ScandirIterator'> ++ [cannot pickle '...' object]
	## +++ <nt.ScandirIterator object at 0x....>
	#### os.walk(...)    --> <class 'generator'> ++ [cannot pickle '...' object]
	## +++ <generator object walk at 0x....>
	__test__types_py()
	
	print("====== TypePrinter Test [END] ======")
	raise Exception("Don't call this in shipped builds")

def __test__types_py(): #>> Special build-ins (types.py)
	print("=== :: Test special build-in :: ===")
	import sys
	def _f(): pass
	class _C:
		def _m(self): pass
	# (\w+?)(?:Type)?( +)= type\((.+)\)      __typePrinter\(\3,\2test="\1"\)
	__typePrinter(_f,                   enum="Function")
	__typePrinter(lambda: None,         enum="Lambda")         # Same as FunctionType
	__typePrinter(len,                  enum="BuiltinFunction")
	__typePrinter([].append,            enum="BuiltinMethod")     # Same as BuiltinFunctionType
	__typePrinter(_C()._m,              enum="Method")
	__typePrinter(_f.__code__,          enum="Code")
	__typePrinter(type.__dict__,        enum="MappingProxy")
	__typePrinter(sys,                  enum="Module")
	__typePrinter(sys.implementation,   enum="SimpleNamespace")
	__typePrinter(type(_f).__code__,    enum="GetSetDescriptor")
	__typePrinter(type(_f).__globals__, enum="MemberDescriptor")
	__typePrinter(object.__init__,      enum="WrapperDescriptor")
	__typePrinter(object().__str__,     enum="MethodWrapper")
	__typePrinter(str.join,             enum="MethodDescriptor")
	__typePrinter(dict.__dict__['fromkeys'], enum="ClassMethodDescriptor")

	def _cell_factory():
		a = 1
		def f(): nonlocal a
		return f.__closure__[0]
	__typePrinter(_cell_factory(),     enum="Cell")

	def _g():  yield 1
	__typePrinter(_g(),                enum="Generator")

	async def _c(): pass
	_c = _c()
	__typePrinter(_c,                  enum="Coroutine")
	_c.close()  # Prevent ResourceWarning

	async def _ag():  yield
	__typePrinter(_ag(),               enum="AsyncGenerator")

	try:   raise TypeError
	except TypeError:
		tb = sys.exc_info()[2]
		__typePrinter(tb,              enum="Traceback")
		__typePrinter(tb.tb_frame,     enum="Frame")
		tb = None; del tb
	#-#####

def __typePrinterLoc(arg, superset=None, full=False, Idx=None):
	""" Shorthand for printing all elements of locals() or globals().
		If superset is given, then only the difference is printed. Store it with _superLoc = [item for item in locals().keys()] """
	valid = arg.keys()
	if not superset is None:
		valid = set(arg.keys()).difference(set(superset)) ## Return all entries of [arg] that do not exist in [superset]
	print("------")
	for elem in valid: __typePrinter(arg[elem], name=elem, full=full, flat=True, Idx=Idx)
	print("------")

def __typePrinterDir(arg, full=False):
	for elem in dir(arg): print(elem); break
	#x = vars(arg)
	""" Shorthand for printing all elements of locals() or globals() """
	for elem in dir(arg): __typePrinter(getattr(arg, elem), name=elem, full=full)

def __typePrinter_List(arg):
	""" Shorthand for printing all elements of a list """
	for (i,elem) in enumerate(arg): __typePrinter(elem, enum=i)

def __typePrinter_Dict(arg, shallow=False):
	""" Shorthand for printing all elements of a dict """
	print(f":: {type(arg)} of length {len(arg)}")
	for (k,v) in arg.items(): __typePrinter(v, enum=k, shallow=shallow)

def __typePrinter(arg, prefix="",name=None,test=None,enum=None, shallow=False,full=False,flat=False,Idx=None):
	"""
	:param arg     [any]          : The object to print
	:param prefix  [str]  = ""    : The prefix to use for each printed line
	:param name    [str]  = None  : if given, print a heading
	:param test    [str]  = None  : if given, set prefix = ":: Test {test:10} :: " & imply shallow
	:param enum    [str]  = None  : if given, set prefix = ":: {enum:15} :: "
	:param shallow [bool] = False : if True, treat containers as empty
	:param full    [bool] = False : if True, print the value
	:param flat    [bool] = False : if True, print non-containers in one line (usually for locals())
	:param idx     [int]  = None  : if flat & given, append [{idx:2}] to the prefix
	
	Both [test] and [enum] also indent their items with ":: {:15} :: "
	Most containers print their first item, if any.
	"""
	if PRODUCTIONFLAG: return
	## https://docs.python.org/3/reference/datamodel.html#object.__len__
	def defines(obj, func): return func in dir(obj)
	rowStart = ""
	if name is not None:
		rowStart = "::{}::".format(name)
		if not flat: print(rowStart)
	if test is not None: prefix = ":: Test {:10} :: ".format(test)
	if enum is not None: prefix = ":: {:15} ::".format(enum)
	recPrefix = prefix
	if flat:
		prefix = f"{prefix}{rowStart:20}"
		if not Idx is None: prefix = f"{prefix}[{Idx:2}]"
	tmp = type(arg)
	try: # missing: __code__, <class 'module'>
		#if defines(arg,'__add__') is False: print(dir(arg))
		#### Special overrides
		if defines(arg, '__call__'): ### def, build-in, lambda
			## missing: if __self__: add 'class' unless in __str__
			print("{} {}".format(prefix, arg))
			return ## instead of "<class 'function'>"
		elif (tmp.__name__ == "Match"): ## result from re.match or re.search
			print(prefix + '<Match: %r, groups=%r>' % (arg.group(), arg.groups()))
			return ## instead of "<re.Match object; span=(2, 3), match='c'>"
		#### String is a Sequence of String
		elif (tmp.__name__ == "str"): ## Avoids infinite recursion
			if flat and full:
				print("{} \"{}\"".format(prefix, arg))
				return
			print("{} {}: len={}".format(prefix, tmp, len(arg)))
			if full: print("\"" + arg + "\"")
			return
		elif (tmp.__name__ == "type"): ## Avoids ['type' object is not iterable]
			print("{} <type '{}'>".format(prefix, arg.__name__))
			return
		########
		#### Print length if Container type
		if defines(arg, '__len__'):
			print("{} {}: len={}".format(prefix, tmp, len(arg)))
			if len(arg) == 0: return
		elif defines(arg, '__length_hint__'): ## For iterator types
			print("{} {}: hint={}".format(prefix, tmp, arg.__length_hint__()))
		elif flat and full:
			print("{} {}".format(prefix, arg)) ## Type is implicit on primitive
		else:
			print("{} {}".format(prefix, tmp))
			if full: print(arg)
		######
		if flat: prefix = recPrefix ## restore prefix for recursion
		if shallow: return
		if [test, enum] != [None,None]: prefix = ":: {:15} ::- ".format("")
		#### Sequence types restricted to 'int'
		if (tmp in [bytearray, bytes, range, slice]): return
		if test is not None: return
		#### Sequence types with any type
		elif (tmp in [list, tuple]) or (tmp.__name__ == 'ndarray'):
			__typePrinter(arg[0], prefix+"0>", full=full, flat=flat)
			if len(arg) == 2: __typePrinter(arg[1], prefix+"1>", full=full, flat=flat)
		#### All other Container types
		elif defines(arg, '__iter__'):
			if defines(arg, '__next__'): ## if already an iterator, avoid changing the object
				x = next(copy.deepcopy(arg))
			else: x = next(iter(arg))
			if defines(arg, '__getitem__'):
				__typePrinter(x, prefix+"Key>", full=full, flat=flat)
				__typePrinter(arg[x], prefix+"Val>", full=full, flat=flat)
			else: __typePrinter(x, prefix+"it>", full=full, flat=flat)
		
		#if defines(arg,'__add__') is False: print(dir(arg))
	except Exception as e:
		print("----- err -----" + str(e))
		print(">Type: {} --> {}".format(tmp.__name__, arg))
	finally:
		if not flat and name is not None: print("------")
