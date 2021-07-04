
# KKPMX


This package is a tool chain to perform necessary edits to exported Koikatsu (KK) Models to be more useful for MMD.


I made it to allow others exploring the possibility of using KK as alternative to searching the Internet for models. Half of the time, the model exists and may even be decently made. But you wouldn't be here if you were satisfied with that. This project might be what you want if any of the following applies to you:

 - You simply cannot find the model you desire or don't trust shady links.
 - The model exists, but may otherwise be incomplete for your purposes (Physics, costume, Doll Anatomy, ...)
 - You want an easy way to (re)create your OC* and making it move over the screen without having to learn / buy sophisticated modeling programs.
    - *... or any target-of-affection, be it waifu or husbando.
 - You already use KK and complain about any restrictions that CharaStudio has when compared with MMD.
 - You already use the Export Mod yourself but realize that a good model takes a lot of effort to just get the basics done.

## Legal (from nuthouse01)


This code is free to use and re-distribute, but I cannot be held responsible for damages that it may or may not cause. You are permitted to examine and modify the code as you see fit, but I make no guarantees about the safety or quality of the result.<br/>
I take no responsibility for how you use this code: any damages, or copyright violations or other illegal activity are completely the fault of the user. These tools only gives you "the ability to read/edit", what you do with that ability is not my business and not my fault.<br/>
You are free to use this for any commercial or non-commercial applications.<br/>
Don't try to claim this work as yours. That would be a profoundly dick move.<br/>
----<br/>
Just to be clear, I extend the above terms to cover this project as well. If you liked it, try visiting nuthouse01's page, as they have a lot of additional great tools and resources to further help out with PMX models in general.


## Links & Credits

 - [nuthouse01](https://github.com/Nuthouse01/PMX-VMD-Scripting-Tools)
 - [PMXExport](https://github.com/TheOddball/KoikatsuPmxExporter/tree/master)
 - [MaterialEditor](https://www.patreon.com/posts/27881027)

## Recommended chain of actions

 1. PMXExport has a weird quirk that messes up the Editor when started the first time after starting Koikatsu.<br/>
Return to the Title Screen and re-enter the Editor to fix it.
 2. Load the desired character and costume.
 3. Change Pose, Expression, Clothing State, or Accessory Visibility as necessary.
    - Recommended: Pose='T-Pose' (one to the left), Blinking=Off, Looking at='Top' (Slider on 0%), Mouth=Neutral.<br/>
Any Eye and/or Mouth Position works, as long as the Eyes stay open and the mouth closed (aka Smiling, Sleepy, ...)
    - While the Tool-Chain is indifferent of whatever pose is used, it might produce funny results in MMD.
    - The same goes for facial expressions, which are further morphed by MMD-Sequences.
 4. Click on [Export] in the upper left corner -- It may take a short moment depending on size.
    - Will add a folder containing the *.pmx + main textures into `C:\koikatsu_model`, named with a random 4-digit number.
       - See the next subsection for how to use the model immediately.
 5. Click on the 'Info' Tab (Heart) and then on [Generate JSON Data].
    - Will add a file called `{CharName}.json` into the same folder.
 6. This step is (almost) entirely optional, but improves the quality of the textures a lot and requires the [MaterialEditor].<br/>
The goal is to go through every asset (Body, Clothes, Accessory) and export the auxiliary textures (in most cases, ColorMask & DetailMask)<br/>
See the [Help]-Section of [Scan Plugin File] for more details of which are currently supported.
    >As [PmxExport] only exports the Main-Texture, you may want to export at least these, if nothing else:
    > - body: overtex1 -- Nips
    > - hitomi: overtex1, overtex2 -- Eye highlights
    - [PmxExport] exports the Main-Texture of all assets, so you can skip them.
    - Note: Some assets lack a Main-Texture (like the default Fox-Tail). If it exists, the ColorMask will instead be used as base texture.
 7. Create a folder called '`extra`' inside the PMX folder.
    - See the [Help]-Section of [Scan Plugin File] for how to use a different name / path.
 8. Move all exported textures into that folder.
    - Main-Textures in this folder take priority over those in the root folder.
 9. Open KKPMX, select option [(5) All-in-one converter] and follow the steps.
    - [Notes for Step(2)]: Recommended choices are: 2 (No) \ 2 (only top-level) \ 1 (Yes)

The model should be (almost) ready, but some last adjustments have to be done manually.

 10. Go to the [TransformView (F9)] -> Search for [bounce] -> Set to 100% -> Menu=[File]: Update Model
 11. [Edit(E)] -> Plugin(P) -> User -> Semi-Standard Bone Plugin -> Semi-Standard Bones (PMX) -> default or all (except `[Camera Bone]`)
 12. When making heavy use of morph sliders, adjust the order of the materials to prevent them getting invisible.

## tl;dr: Minimum steps to make the exported model work immediately


If you just want to test out some things with minimum set of work, perform these steps:

 1. You only need the [PMXExport] Plugin for this. Do the first 4 Steps in the above list.
 2. Open the *.pmx file and go to the Materials Tab
 3. There are two assets called 'Bonelyfans'; Set their Opacity to 0 & tick off [Edge Outline]
 4. Go to the 'Display' Tab
 5. Go through all Display-Frames: Delete any '-1' Elements appearing in the right box

The model should now work properly in MMD, but may perform weird with most TDA Dances. To further fix that:

 6. Go to the [TransformView (F9)] -> Search for [bounce] -> Set to 100% -> Menu=[File]: Update Model
 7. [Edit(E)] -> Plugin(P) -> User -> Semi-Standard Bone Plugin -> Semi-Standard Bones (PMX) -> default or all (except `[Camera Bone]`)

## To compile it yourself


To compile the project yourself, you need to install the following dependencies:

 - Tool-Chain
    - The tool was compiled and tested with Python 3.8+.
    - To use 'kkpmx_property_parse.py', you need to install ['cv2', 'numpy', 'blend_modes']
    - To use 'kkpmx_handle_overhang.py', you need to install ['numpy', 'scipy', 'sympy']
    - Download [nuthouse01]'s tool (pre v6.0) and extract it somewhere
    - Copy the contents of KKPMX's 'src' folder into '[nuthouse01]/python', overwrite if necessary. The changes in question are:
       - [morph_scale.py] `get_idx_in_pmxsublist()`: Extra argument to suppress 'Not found' warning to verify valid inputs when asking for materials.
       - [nuthouse01_core.py] `prompt_user_filename()`: Ignore "" around File-Paths to allow drag-drop of files into the CommandWindow.
       - [file_sort_textures.py] `main()`: Isolated initialization to allow calling with existing PMX instance.
       - [model_overall_cleanup.py] `main()`: Isolated initialization to allow calling with existing PMX instance.
       - [_alphamorph_correct.py] `template, template_minusone()`: Don't zero out morph colors.
 - KK Mod
    - The Mod has been compiled and tested with .NET 3.5 (same as KK)
    - All necessary packages can be installed by "Restore Packages".
    - After compilation, put the *.dll into `{KK-Folder}/BepInEx/plugins`

## Help


The following section enumerates the available functions when starting [kkpmx_core].


Most modes will always create a new file and append a suffix (see [Output]).

### (0) Show help for all

>  Displays the info available in this section.

### (1) Cleanup Model

>  This is one of two main methods to make KK-Models look better.
>  It does the following things:
>  
>  - disable "Bonelyfans", "Standard" (+ emblem if no texture)
>  - Simplify material names (removes "(Instance)" etc)
>  - if tex_idx != -1: Set diffRGB to `[1,1,1]` ++ add previous to comment
>  - else:             Set specRGB to `[diffRGB]` ++ add previous to comment
>  - Set toon_idx = "toon02.bmp"
>  - Rename certain bones to match standard MMD better
>  - Only for KK-Models:
>  -  - Adjust Ankle Bones to avoid twisted feet
>  -  - Adjust Skirt physics
>  -  - Add Hair physics
>  - Remove items with idx == -1 from dispframes `[<< crashes MMD]`
>  - Fix invalid vertex morphs `[<< crashes MMD]`
>  
>  In some cases, this is already enough to make a model look good for simple animations.
>  
>  Output: PMX File '`[filename]`_cleaned.pmx'

### (2) Make Material morphs

>  Generates a Material Morph for each material to toggle its visibility (hide if visible, show if hidden).
>  - Note: This works for any model, not just from KK (albeit accuracy might suffer without standard names).
>  
>  #### Names & Bones
>  - If the materials have only JP names, it attempts to translate them before using as morph name (only standard from local dict).
>  - Assuming material names have indicative/simple names, also attempts to guess the role of a material
>    - (== part of the body, a piece of clothing, an accessory) and generates groups based upon that.
>    - Body parts will stay visible, but clothes / accessories can be toggled off as a whole.
>  - If the model has a standard root bone ('全ての親'), adds a morph to move the model downwards.
>    - Can be used as an alternative for moving the body downwards in MMD (e.g. when hiding shoes).
>  - If the model has a standard center bone ('センター'), adds a morph to move the body downwards.
>    - Can be used to test physics better in TransformView.
>  
>  #### Using the Plugin
>  - If the model has been decorated with Plugin Data, then the following groups will be added as well:
>    - Head Acc   :: Accessories attached to hair, head, or face
>    - Hand/Foot  :: Accessories attached to wrist, hand, ankle, or foot; incl. gloves, socks, and shoes
>    - Neck/Groin :: Accessories attached to the neck, chest, groin, or rear
>    - Body Acc   :: Accessories attached to the body in general (arms, shoulder, back, waist, leg)
>    > Tails, if recognized as such, will be considered part of the body and are always visible.
>  
>  #### Combination rules
>  - The order of operations makes no difference in effect.
>  - Every material has its own MorphToggle, except if the user declined the inclusion of body parts recognized as such.
>  - Recognized Body parts are excluded from all "Hide all" and "Show all" morphs.
>  - If an individual morph makes a material visible again, it can be hidden by the "Hide all" morph.
>  - If an individual morph hides a material, it can be made visible again with the "Show X" morph.
>  - If a material has been hidden by any "Hide all X" morph, it can be made visible again with its "Show X" morph.
>  
>  Output: PMX file '`[modelname]`_morphs.pmx'

### (3) Scan Plugin File

>  This is the second of two main methods to make KK-Models look better.
>  - Note: Current/Working directory == same folder as the *.pmx file.
>  - Within the *.json file, this is abbreviated as "%PMX%".
>  
>  It will parse a processed plugin file and apply colors and shaders, as well as combining textures.
>  It also sets the visibility on customized multi-part assets and adds the accessory slots into the comment.
>  - Remarks: All texture adjustments work based on "Garbage in, Garbage out": The results are only as good as the sum of the sources.
>  
>  This does require some preparations before it can be used:
>  1. A *.json file generated by `[(7) GenerateJsonFile]`
>  - Default looks for "#generateJSON.json" in the working directory
>  - Otherwise asks for the path if not found
>  2. A folder filled with extra textures exported from KK (requires the `[MaterialEditor]` mod)
>  - The path will be read from the above *.json in "options" > "base" and defaults to "./extra".
>  - Currently working / supported are:
>    - MainTex (already exported by `[PMXExport]`, so can be ignored)
>    - DetailMask
>    - ColorMask
>    - overtex1 (on body and eye)
>    - overtex2 (on eye)
>  - Not (yet) supported are:
>    - on body: overtex2
>    - on face: overtex1, overtex2, overtex3
>    - LineMask, NormalMap, NormalMask
>  
>  Additional notes:
>  - After generation, the *.json file can be edited to change some aspects (some colors, visibility, textures) without KK. Re-run this to apply changes.
>  - Due to pre-generation, sometimes textures are used that do not exist (which will print a warning). Remove the item from the faulty material's template to clear the warning.

### (4) Isolate protruding surfaces

>  Scans the given material(s) against bleed-through of vertices / faces poking through the surface of another.
>  > Currently will only find all protrusions going towards negative Z-Axis, and may not work for X or Y Axis.
>  
>  The initial bounding box is defined by the base material which the target is checked against
>  - Example: `[Base]` Jacket vs. Vest \ `[Target]` Body ::: Look where the body is visible through clothes
>    - Jacket: Bounding Box goes from wrist to wrist, and neck to waist. It won't scan Hands or the lower body
>    - Vest:   Bounding Box stops at the shoulders --- That means it will ignore the arms as well.
>  
>  There are three options to define the coordinates of a bounding box. All vertices outside it will be ignored.
>  - Choose best-guess defaults to remove chest protrusions on a KK-Model
>  - Input manual coordinates (for either a scan or box cut)
>  - Full scan (== full box of target against full box of base)
>  The smaller it is, the less calculations are performed and it will complete faster.
>  
>  Output: PMX file '`[modelname]`_cutScan.pmx'
>  - As opposed to usual, will count up instead of appending if '_cutScan' is already part of the filename

### (5) All-in-one converter

>  All-in-one Converter
>  
>  Assuming a raw, unmodified export straight from KK, this will perform several tasks.
>  All of which can be done individually through either the above list or the GUI of nuthouse01.
>  - `[ - ]` Creating a backup file with "_org" if none exists
>  - `[ 1 ]` Main cleanup of the model to make it work in MMD
>  - `[7 3]` Asking for the *.json generated by the plugin & parsing it into the model
>  - `[Gui]` Renaming & Sorting of Texture files (== "file_sort_textures.py")
>  - `[1-2]` Apply several rigging improvements
>  - `[ 2 ]` Optional: Adding Material Morphs to toggle them individually
>  - `[Gui]` Running a general cleanup to reduce filesize (== "model_overall_cleanup.py")
>    - This will also add translations for most untranslated phrases in the model
>  - `[ - ]` If initially requested to not store per-step modifications, the model will be saved at this point.
>  - `[ 4 ]` Optional: Trying to fix bleed-through texture overlaps (within a given bounding box)
>    - Warning: Depending on the model size and the chosen bounding box, this can take some time.
>    - -- One can choose between "Scan full material" | "Input manually" | "Restrict to Chest area"
>    - This will always generate a new model file, in case results are not satisfying enough
>  
>  There are some additional steps that cannot be done by a script; They will be mentioned again at the end
>  - Go to the `[TransformView (F9)]` -> Search for `[bounce]` -> Set to 100% -> Menu=`[File]`: Update Model
>  - `[Edit(E)]` -> Plugin(P) -> User -> Semi-Standard Bone Plugin -> Semi-Standard Bones (PMX) -> default or all (except `[Camera Bone]`)

### (6) ----------

>  Separator between Main and Minor Methods. Will exit the program if chosen.

### (7) Parse Result from Plugin

>  Parses the raw output from the `[KKPMX]` mod.
>  The result can be found in the same folder as `[PmxExport]` puts its models ("C:\koikatsu_model")

### (8) Export Material to CSV

>  Input: STDIN -> Material ID or name, default = cf_m_body <br/>
>  Input: STDIN -> Offset to shift vertices (updates ref in faces) <br/>
>  
>  Export a material with all faces and vertices as *.csv. <br/>
>  The default operation of the editor only writes the material + faces but leaves out the vertices.
>  
>  An optional offset can be used to allow re-importing it later without overriding vertices.
>  - Note: Vertices are imported first, and will be adjusted by the editor to start at the first free index
>    - Which will mess up the references in the faces, so make sure the first vertex index is correct.
>  
>  Output: CSV file '`[modelname]`_`[mat.name_jp]`.csv'

### (9) Move material weights to new bones

>  Input(1): STDIN -> Material ID or name, default = cf_m_body <br/>
>  Input(2): STDIN -> Flag to create a root bone to attach all new bones to. <br/>
>  Loop Input: STDIN -> Bone ID to move weights away from <br/>
>  
>  Output: PMX file '`[filename]`_changed.pmx'
>  
>  Moves all bone weights of a given material to a copy of all affected bones.
>  The optional flag controls which parent the new bones use:
>  - Yes / True --> Create a new bone to use as parent for all
>  - No / False --> Set the original bone as parent of the new.
>  - The parent itself will use ID:0 (root) as parent
>  
>  Bones are reused if they already exist:
>  - If used, the parent itself will be called '`[mat.name_jp]`_root' // @verify
>  - With parent, new bones are called '`[bone.name]`_`[mat.name_jp]`'
>  - Otherwise,   new bones are called '`[bone.name]`_new'
>  
>  In terms of manual actions, this has a similar effect as:
>  - Removing all other materials in a separate copy
>  - Renaming all bones used by the chosen material
>  - Re-Import into the current model to replace the old material
>  - Setting parent bones correctly (with regards to `[common parent]`)
>  
>  Potential uses for this are:
>  - Adding physics that only affect a material instead of multiple (which is common with KK-Models)
>  - With a common parent, it can act as independent entity (similar to how it is in KK-Models)
>    - Being detached from normal bones, they require own rigging since KK-Export only does it for skirts
>    - This also allows utilizing the "outside parent" (OP) setting in MMD without the need of individual *.pmx files
>    - which is usually required (but also more powerful) for things like throwing / falling of clothes

### (10) Print material bones

>  Input: STDIN -> Ask for Material ID or name <br/>
>  	Action: mat -> faces -> vertices -> bones <br/>
>  	Output: STDOUT -> Unique list of used bones (Format: id, sorted) <br/>

### (11) Slice helper

>  Cuts a surface along given vertices and allows them to be pulled apart at the new gap.
>  It is recommended that the vertices form one continuous line; Use the `[Selection Guide]` for help.
>  - The order of the vertices does not matter, as long as all can be lined up to form one clean cut.
>  It will generate two morphs to pull the seam apart. For that it will ask which direction is "Up" and which is "forward"
>  - In most cases, the angle of the morphs has to be adjusted manually.
>  
>  Example: To cut a vertical window (== rotated capital H): (aligned to Y-Axis; Rotate the instructions depending on the chosen "Up" Direction)
>  1. Lasso-select the vertex path and note the vertices with `[Selection Guide]`
>  2. Perform a cut with 25 (or 24 on the back) -- This is the 'bridge' of the "H"
>     - This means starting this mode, then using options '2' and ('5' or '4')
>  3. Select either head or tail of the line (including the newly added vertex) and add their direct neighbour on the left and right
>  4. Perform a cut with 05 (04 on the back) -- 'Old' Morph opens upwards
>  5. Repeat `[3]` for the other tail / head
>  6. Perform a cut with 15 (14 on the back) -- 'Old' Morph opens downwards
>  
>  Note: Unless there is an explicit need to keep them separate, Step `[3]` and `[5]` can be combined, as their morphs produce messy results most of the time and can be deleted, keeping only the initial 2 from Step `[2]`.

### (12) Run Rigging Helpers

>  Rigging Helpers for KK.
>  - Adjust Body Physics (so far only adjusts the Rear RigidBody)
>  - Transform Skirt Grid from Cubicle to Rectangles
>  - Rig Hair Joints
>  -  - Since KKExport loves to merge vertex meshes if they are bound to bones sharing the same name, this also corrects the bone weights
>  -  - The "normal" rigging can also be reproduced by selecting a linked bone range, and opening `[Edit]`>`[Bone]`>`[Create Rigid/Linked Joint]`
>  -  - Sometimes needs minor optimizations, but also allows a bit of customization (by changing the Rigid Type of the chain segments)
