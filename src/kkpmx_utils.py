# Cazoo - 2021-05-13
# This code is free to use and re-distribute, but I cannot be held responsible for damages that it may or may not cause.
#####################
### sys
import json
import os
import re
import copy

### Library
import nuthouse01_core as core
#import nuthouse01_pmx_parser as pmxlib
#import nuthouse01_pmx_struct as pmxstruct
#import morph_scale
### 

def main_starter(callback):
	"""
	Quickstarter for running from console
	
	## Template
	def run(pmx, input_filename_pmx): pass
	if __name__ == '__main__': util.main_starter(run)
	"""
	import nuthouse01_pmx_parser as pmxlib
	# prompt PMX name
	core.MY_PRINT_FUNC("Please enter name of PMX input file:")
	input_filename_pmx = core.MY_FILEPROMPT_FUNC(".pmx").strip('"')
	pmx = pmxlib.read_pmx(input_filename_pmx, moreinfo=True)
	core.MY_PRINT_FUNC("====---====")
	callback(pmx, input_filename_pmx)
	core.MY_PRINT_FUNC("====---====")
	core.MY_PRINT_FUNC("Done!")

#def get_parent_bone(pmx, name):
#	pidx = pmx.bones[find_bone(pmx, name)]
#	if pidx: return pmx.bones[pidx.parent_idx]
#	return None

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
		result = None
		try:
			result = json.loads(json_message)
		except Exception as e:
			# Only continue on invalid escapes
			if str(e).find("Invalid \escape") == -1:
				print(e)
				return None
			print(e)
			# Find the offending character index:
			#idx_to_replace = int(e.message.split(' ')[-1].replace(')',''))
			idx_to_replace = int(str(e).split(' ')[-1].replace(')', ''))
			
			# Remove the offending character:
			json_message = list(json_message)
			json_message[idx_to_replace] = ''
			new_message = ''.join(json_message)
			return fix_JSON(json_message=new_message)
		return result
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
		with open(path, 'r') as myfile: raw_data = myfile.read()
	except Error as e:
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

def ask_yes_no(message, default=None):
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
	copy2(src, dst)
	
def is_number(text):
	try:
		return float(text) is not None
	except:
		return False

######
## Finders
######

def find_bone(pmx,name,e=True):  return morph_scale.get_idx_in_pmxsublist(name, pmx.bones,e)
def find_mat(pmx,name,e=True):   return morph_scale.get_idx_in_pmxsublist(name, pmx.materials,e)
def find_disp(pmx,name,e=True):  return morph_scale.get_idx_in_pmxsublist(name, pmx.frames,e)
def find_morph(pmx,name,e=True): return morph_scale.get_idx_in_pmxsublist(name, pmx.morphs,e)
def find_rigid(pmx,name,e=True): return morph_scale.get_idx_in_pmxsublist(name, pmx.rigidbodies,e)

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
	__typePrinter(iter(a))          # == readonly iter <T>				             __hash__, __iter__, __next__, __length_hint__
	__typePrinter(iter(d))          # == readonly iter <T>				             __hash__, __iter__, __next__, __length_hint__
	__typePrinter(iter(d.values())) # == readonly iter <T>				             __hash__, __iter__, __next__, __length_hint__
	#>> list_iterator, dict_keyiterator, dict_keys([<<contents>>])
	__typePrinter(zip(a,b))         # == ... \\ no __getitem__			             __hash__, __iter__, __next__
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

def __typePrinterLoc(arg):
	""" Shorthand for printing all elements of locals() or globals() """
	for elem in arg: __typePrinter(arg[elem], name=elem)

def __typePrinter_List(arg):
	""" Shorthand for printing all elements of a list """
	for (i,elem) in enumerate(arg): __typePrinter(elem, enum=i)

def __typePrinter_Dict(arg, shallow=False):
	""" Shorthand for printing all elements of a dict """
	for (k,v) in arg.items(): __typePrinter(v, enum=k, shallow=shallow)

def __typePrinter(arg, prefix="",name=None,test=None,enum=None, shallow=False):
	## https://docs.python.org/3/reference/datamodel.html#object.__len__
	def defines(obj, func): return func in dir(obj)
	if name is not None: print("::{}::".format(name))
	if test is not None: prefix = ":: Test {:10} :: ".format(test)
	if enum is not None: prefix = ":: {:15} :: ".format(enum)
	tmp = type(arg)
	try: # missing: __code__, <class 'module'>
		#if defines(arg,'__add__') is False: print(dir(arg))
		#### Special overrides
		if defines(arg, '__call__'): ### def, build-in, lambda
			## missing: if __self__: add 'class' unless in __str__
			print("{} {}".format(prefix, arg))
			return ## instead of "<class 'function'>"
		elif (tmp.__name__ == "Match"): ## result from re.match or re.search
			print('<Match: %r, groups=%r>' % (match.group(), match.groups()))
			return ## instead of "<re.Match object; span=(2, 3), match='c'>"
		#### String is a Sequence of String
		elif (tmp.__name__ == "str"): ## Avoids infinite recursion
			print("{} {}: len={}".format(prefix, tmp, len(arg)))
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
		else:
			print("{} {}".format(prefix, tmp))
		######
		if shallow: return
		if [test, enum] != [None,None]: prefix = ":: {:15} :: ".format("")
		#### Sequence types restricted to 'int'
		if (tmp in [bytearray, bytes, range, slice]): return
		#### Sequence types with any type
		elif (tmp in [list, tuple]) or (tmp.__name__ == 'ndarray'):
			__typePrinter(arg[0], prefix+"0>")
			if len(arg) == 2: __typePrinter(arg[1], prefix+"1>")
		#### All other Container types
		elif defines(arg, '__iter__'):
			if defines(arg, '__next__'): ## if already an iterator, avoid changing the object
				x = next(copy.deepcopy(arg))
			else: x = next(iter(arg))
			if defines(arg, '__getitem__'):
				__typePrinter(x, prefix+"Key>")
				__typePrinter(arg[x], prefix+"Val>")
			else: __typePrinter(x, prefix+"it>")
		
		#if defines(arg,'__add__') is False: print(dir(arg))
	except Exception as e:
		print("----- err -----" + str(e))
		print(">Type: {} --> {}".format(tmp.__name__, arg))
	finally:
		if name is not None: print("------")
