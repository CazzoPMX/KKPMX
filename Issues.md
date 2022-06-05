
# Known Issues / Questions





If you know of any tips or tricks on what would be useful in the script (like, specific physics, or 'I use X often, could you add it as pattern'), just tell me and I see what I can do.


## Previously asked questions


Recollection of certain answers given as part of an issue.

 - [I need help with [Mode 04], can you help me out?](https://github.com/CazzoPMX/KKPMX/issues/4#issuecomment-1122760640)

## Troubleshooting


This section contains a list of known issues, and how to solve them.


### KK and PMXEditor issues


| General issues with Export | |
| --- | --- |
| Button does not appear | If you installed the DLL with KKManager, sometimes(?) the DLL is placed into [<Folder of KK>\BepInEx]. In that case, move the DLL into [<Folder of KK>\BepInEx\plugins] and restart KK. |
| Incomplete exports | Custom Head Shapes (especially if they do not use all 'common elements', e.g. no or renamed eyebrows, tongue etc.) can cause the Exporter to fail in the Editor. It seems to work when exporting from CharaStudio though. |
| Incomplete exports (Studio) | However, with Exporter enabled(TBD), the Studio is sometimes(?) unable to work with AdvancedBones, so they will stay unmodified. |
| Nothing is exported | Could be because something goes wrong and the mod is unable to create the folder at [C:\koikatsu_model]. Please create the folder yourself and try again. |

| Working with PMXEditor | |
| --- | --- |
| All morphs are empty after I applied Bounce!  | Originally being Japanese, PMXEditor only works with English decimal separators; if your Regional Language settings happen to use '1,5' instead of '1.5',<br/>the only solution is to change the Decimalseparator used by your system (usually found in the Formats tab under 'Region and Language')<br/>This will not change how the separator is typed by the numpad, though. |
| CSV imports / export don't work! | Same problem as above |

### MMD issues


| MMD crashes when loading | |
| --- | --- |
| [Display-Frames] contain '-1' entries | Export-Issue fixed by (1-Cleanup) |
| VertexMorphs link to non-existing indices | Export-Issue fixed by (1-Cleanup) |
| Joints missing one or both Rigids |     |
| The model tries to show (in total) more than 250 morphs. |     |
| Project refuses to load but Model is fine. | Try opening the project by dragging the *.pmm onto the MikuMikuDance.exe directly. |

| MMD crashes randomly | |
| --- | --- |
| Sometimes caused by Physics calculation. | Set MMD to 'No calculation' or 'Trace' before loading so that the error can be identified |

| Other | |
| --- | --- |
| Non-see-through layers while fading out | Put Materials in correct order (inside index < outside index) e.g. bra,shirt,jacket or pantsu,skirt |
| Unable to see facial frames | Add missing Material-Morphs to [Facials] Frame |
| [Facials] tab takes long to load | Remove the [Expression] morphs from [Facials].<br/>Done by (3:Material-Morphs), but readded by [GUI] |
| Vibrating chest physics | Locate the 'stick' Rigids and set ROT.Z = max:1 min:0 |
| Bones and Physics are connected all over the place | Because there is no enforced naming convention for custom accessories except for the start,<br/>most accessories (except a certain few groups) are rigged as "all in a line".<br/>Besides a certain few exceptions that added a big enough number of assets (like hair mods),<br/>most will therefore be all over the place, especially if they are imported from another game.<br/>Certain obvious cases have been added through [Step 06 of Rigging], but manual clean up and properly cutting<br/>into segments is required for proper use of most other cases. Mode:03 of the Rigging Func can be used to help with that. |
| Hair flies away like paper lanterns | Physics chains need two solid segments to stay where they are. (At least they didn't stay unless I did that) |
| Some Textures have wrong colors | If texture color is supplied through the texture itself, the default color usually stays, which is then applied as 'expected' through Color & DetailMask. Delete the masks which cause the problems and run Mode:3 (Property Parser) again (or repair the filepaths manually yourself) AND/OR set the colors correctly in KK. |
| Eyes have wrong offset | Depending on weird internals, the 'idle' position of the eyes without blinking or following can be such that the Render-State exports that with -0.1 resp. 0.1. Just replace them in 'cf_m_hitomi_00#-<<number>>'.Offset with 0.0 (or at least equal on both 'hitomi' entries, if they are bigger.). Same for scale |
| Skirt being weird after rigging mode | Sometimes the numbers are exported weirdly, and cause one specific line of skirt rigging to be inverted. Just put a '-' infront of the [Rot.X] value of all 5 and it should be fine again. |
| [KKS] See-through face | It seems KKS uses transparency where the blush stickers are applied. For the time being, please use any layer-based image editor to manually merge the face texture on top of overtex2. |
| Hair texture mismatch | I 'think' it happens when a model uses any accessory multiple times (which hair often does) but not all use the same texture masks (== Color,Detail,Alpha).<br/>This can be solved by adding an explicit Texture override as described in 'Customize.md' and then running the PropertyParser again. |

## Open Issues


Things that are worked on or haven't been fixed yet.

 - Extra textures for face are ignored. -- overtex2 stays optional
 - Knee looks broken when kneeling too much.
    - It seems that in most motions, this can be fixed by 'not moving the leg too far', as it is simply an IK-Limit issue. Haven't figured out the correct numbers yet though
 - AlphaMask on Clothes.
 - Find a better solution for when a model uses an asset multiple times but they are not sharing the same texture. (without generating a million files)