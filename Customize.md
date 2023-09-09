
# To compile it yourself


To compile the project yourself, you need to install the following dependencies:

 - Tool-Chain
    - The tool was compiled and tested with Python 3.8+. (currently using 3.10)
    - To use 'kkpmx_property_parse.py', you need to install ['numpy', 'opencv-python', 'blend_modes']
    - To use 'kkpmx_handle_overhang.py', you need to install ['numpy', 'scipy', 'sympy']
    - If scipy causes issues, install it manually from https://www.lfd.uci.edu/~gohlke/pythonlibs/#scipy
    - I added all necessary files myself, but in case you are interested, they are based on [nuthouse01]'s tool (pre v6.0)
       - If you do it yourself, copy the contents of KKPMX's 'src' folder into '[nuthouse01]/python', overwrite if necessary. The changes in question are:
       - [morph_scale.py] `get_idx_in_pmxsublist()`: Extra argument to suppress 'Not found' warning to verify valid inputs when asking for materials.
       - [nuthouse01_core.py] `prompt_user_filename()`: Ignore "" around File-Paths to allow drag-drop of files into the CommandWindow.
       - [file_sort_textures.py] `main()`: Isolated initialization to allow calling with existing PMX instance.
       - [model_overall_cleanup.py] `main()`: Isolated initialization to allow calling with existing PMX instance.
       - [_alphamorph_correct.py] `template, template_minusone()`: Don't zero out morph colors.
       - [_dispframe_fix.py.py] `dispframe_fix()`: Add additional morphs to a new 'moremorphs' display so that user-defined morphs are removed last when capping the list.
 - KK Mod
    - The Mod has been compiled and tested with .NET 3.5 (same as KK)
    - All necessary packages can be installed by "Restore Packages".
    - After compilation, put the *.dll into `{KK-Folder}/BepInEx/plugins`

# JSON Structure





All values must be either a dict {}, an array [], a number, or enclosed in "".<br/>
The Entries are read as `'Name': 'DataType' -- 'Description'`


## General terms

 - `NAME_M`: string -- The name of the material (owns textures), taken as-is from in-game, extended with the parent slot.
 - `NAME_R`: string -- The name of the render (owns vertices & faces), taken as-is from in-game, extended with the parent slot.
 - `Parent slot (Body / Clothes)`: string -- '\#' \+ internal instance id of in-game object.
 - `Parent slot (Accessories)`: string -- '\@' \+ 'ca_slot' \+ Zero-based slot index.
 - `Asset`: Game object -- Refers to a fully defined game object (e.g. a piece of clothing, an accessory, etc.).
   - `Render`: Physical mesh -- When opening the MaterialEditor (ME), one of the entries labeled 'Renderer'.
   - `Material`: Shader engine -- When opening the ME, one of the entries labeled 'Material'.
     - `Shader`: Internal processor -- When opening the ME, the dropdown labeled 'Shader'. Determines available textures & parameters.
     - `Texture`: Shader input -- When opening the ME, one of the rows containing the 'Export' and 'Import' buttons.
     - `Parameter`: Shader attribute -- When opening the ME, one of the configurable values below the textures.
     - `Property`: Meta attribute -- Refers to non-parameter attributes added by the mod for processing.
 - `%PMX%`: Placeholder -- Represents the directory path of the \*.pmx file. Will be replaced by the script when reading the file.

## The #generateJSON.json used by 'Mode 03'

 - `name`: string -- The name to write into the 'Info' Tab.
 - `options`: dict -- General properties.
   - `use_english`: bool -- Default true -- Control if the english or japanese name of a material is used for default texture paths.
   - `base`: string -- Base directory to use for generating default texture paths. Default is "%PMX%/extra".
   - `process_hair`: bool -- Default true. If false, all hair materials will be skipped.
 - `<List of Body Materials>`: &lt;Material> -- The corresponding entries for body `[== 2nd Menu in CharEditor]`.
 - `<List of Face Materials>`: &lt;Material> -- The corresponding entries for face, eyes, nose, mouth `[== 1st Menu in CharEditor]`.
 - `<List of Hair Materials>`: &lt;Material> -- The corresponding entries for hair `[== 3rd Menu in CharEditor]`.
 - `<List of Clothing Materials>`: &lt;Material> -- The corresponding entries for main clothes `[== 4th Menu in CharEditor]`.
 - `<List of Accessory Materials>`: &lt;Material> -- The corresponding entries for accessories `[== 5th Menu in CharEditor]`.

One Material entry consists of...

 - `<NAME_M>`: dict -- The actual Material.
   - `available`: array -- List of textures the shader supports in the game.
   - `textures`: array -- The textures actually used by the script.
   - `shader`: string -- The processing mode to use inside the script. Look them up in the source-code if you want to know.
   - `<List of Parameters>`: &lt;varies> -- The Parameters as found in the corresponding entry within the raw \*.json file.
   - `<Texture overrides>`: string -- The entries of `[textures]` can be explicitly defined to provide custom texture paths, as opposed to auto-generated ones. Use two slashes `[\\]` instead of one..
       - Example: `"AlphaMask": "%PMX%\\MyAlphaTexture.png",` will use that AlphaMask instead of the generated default, which would be `"AlphaMask": "%PMX%\\extra\\" + NAME_M + "_AlphaMask.png",`.
   - `template`: bool -- 'true' tells the parser that this is not a fully defined material (aka is used for 'inherit').
 - `<NAME_R>`: dict -- The associated Render. Can appear multiple times if the Asset contains as such (called \*1, \*2, ... then).
   - `meta`: dict -- Groups meta properties.
     - `enabled`: bool -- Material is visible yes/no.
     - `receive`: bool -- Inherit shadows yes/no.
     - `shadows`: one of ['On', 'ShadowsOnly', 'Off'] -- Cast shadows yes/no.
     - `render`: NAME_R:raw -- The render name as-is.
     - `parent`: string -- The internal asset slot (== Category) that owns this asset. Always starts with 'ct_'.
     - `slot`: string -- The actual slot of the root bone.
   - `inherit`: &lt;NAME_M> -- The material to copy the properties from. If false, expects that the above material properties follow.

## The raw *.json from the Exporter [processed by 'Mode 07']

 - `meta`: dict -- General properties.
   - `name`: string -- The name to add to in the Info Tab.
   - `resetEyes`: bool -- if 'True', overwrites the eye offset with (-0.5, -0.5).
 - `render`: dict -- Collection of Render entries.
   - `<NAME_R / Render>`: dict -- One of the Render meshes used by the model.
     - `enabled`: bool -- Material is visible yes/no.
     - `shadows`: one of ['On', 'ShadowsOnly', 'Off'] -- Cast shadows yes/no.
     - `receive`: bool -- Inherit shadows yes/no.
     - `render`: NAME_R:raw -- The render name as-is.
     - `parent`: string -- Slot name.
     - `mat`: List&lt;NAME_M> -- A list of materials that this render uses. Usually one.
 - `mat`: dict -- Collection of Material entries.
   - `<NAME_M / Material>`: dict -- One of the Materials attached to an asset, see MaterialEditor.
     - `offset`: tuple -- X / Y offset for the Main texture (ignored except on hitomi).
     - `scale`: tuple -- X / Y scale for the Main texture (ignored except on hitomi).
     - `token`: NAME_M:raw -- The raw material name as returned from Unity.
     - `shader`: string -- The shader used by the selected material.
     - `<List of in-game parameters>`: &lt;varies> -- A subset of parameters used by the shader.

Note: Although only used parameters are exported by the mod, anything that starts with '_' (+ the four at the top) is parsed into #generateJSON.json
