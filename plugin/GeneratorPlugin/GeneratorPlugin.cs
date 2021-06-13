using BepInEx;
using System;
using System.Text;
using UnityEngine;
using System.Text.RegularExpressions;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using KKAPI.Studio;
using KKAPI.Maker;
using KKAPI.Maker.UI;

namespace GeneratorPlugin
{
    [BepInPlugin(GUID, "JSON Generator Plugin", Version)]
    public class GeneratorPlugin : BaseUnityPlugin
    {
        public const string GUID = "aa2g.kant.rim.remover";
        public const string Version = "1.1";

		internal static GeneratorPlugin Instance;

        internal void Awake() {
			Instance = this;
        	if (StudioAPI.InsideStudio) return;

			GeneratorGui.Initialize();
        }
	}

	internal class GeneratorMain {

		static string[] colorTags = (new [] {
				"_Color", "_Color2", "_Color3", "_Color4",
				"_overcolor1", "_overcolor2", "_overcolor3",
				"_ShadowColor", "_SpecularColor", "_LineColor",
				/* From [eye] */"_shadowcolor",
			}).OrderBy(x => x).ToArray();

		static string[] renderTags = (new [] {
				// Common for most
				"_rimpower", "_rimV", "_ShadowExtend", "_SpecularPower",
				// main_skin
				"_DetailNormalMapScale", "_linetexon", "_tex1mask",
				"_nip", "_nipsize",	"_nip_specular", "_notusetexspecular",
				// main_opaque
				"_DetailBLineG", "_DetailRLineR", //"_notusetexspecular",
				"_ShadowExtendAnother", "_SpeclarHeight", "_SpecularPowerNail",
				///* main_alpha */ "_DetailBLineGA","_outline",
				/* toon_eye_lod0 */ "_exppower", "_isHighLight", "_rotation",
				//-----
				///* AlphaMask */ "_alpha_a", "_alpha_b",
				/* AnotherRamp */"_AnotherRampFull",
				///* DetailMap */ "_DetailBLineG", "_DetailRLineR",
				/* LineMask */ "_LineWidthS",
			}).OrderBy(x => x).ToArray();
		
		internal static void Generate(GameObject o, string prefix, string fullname) {
			StringBuilder sbR = new StringBuilder();
			StringBuilder sbM = new StringBuilder();
			string docStart  = "\n{";                        // {
			string catStart  = "\n  \"{0}\": {{";            //   "cat": {
			string fmtStart  = "\n\t\"{0}\": {{";            // 	"name": {
			string fmtLine   = "\n\t\t\"{0}\": {1},";        // 		"key": value,
			string fmtLineS  = "\n\t\t\"{0}\": \"{1}\",";    // 		"key": "value",
			string fmtStartM = "\n\t\t\"{0}\": [";           // 		"key": [
			string fmtLineM  = "\n\t\t\t\"{0}\",";           // 			"value",
			string fmtEndM   = "\n\t\t],";                   // 		],
			string fmtEnd    = "\n\t},";                     // 	},
			string catEnd    = "\n  },";                     //   },
			string docEnd    = "\n},";                       // },
			string fmtColor  = "[ {0}, {1}, {2}, {3} ]";     // [ R, G, B, A ]
			var tabu = new List<string>();

			sbR.AppendFormat(catStart, "render");
			sbM.AppendFormat(catStart, "mats");
			foreach (var r in o.GetComponentsInChildren<Renderer>()) {
				//if (!(r != null && r.materials != null)) continue;
				if (!(r != null && r.materials != null)){
					var rr = r?.name ?? "<render=null>";
					Console.WriteLine("Invalid Render: " + rr);
					continue;
				}
				var parent = FindParent(r.transform);
				var tokenR = GetName(r, r.name, parent);
				sbR.AppendFormat(fmtStart, tokenR);
				// Using "LoadCharaFbxDataAsync", these do not reflect the local changes
				sbR.AppendFormat(fmtLineS, "enabled", r.enabled);
				sbR.AppendFormat(fmtLineS, "shadows", r.shadowCastingMode);
				sbR.AppendFormat(fmtLineS, "receive", r.receiveShadows);
				sbR.AppendFormat(fmtLineS, "render", r.name);
				sbR.AppendFormat(fmtLineS, "parent", parent);
				sbR.AppendFormat(fmtStartM, "mat");
				foreach (var mat in r.materials) {
					if (mat == null) continue;
					var token = GetName(mat, mat.name, parent);
					
					sbR.AppendFormat(fmtLineM, token);
					if (tabu.Contains(token)) continue;
					tabu.Add(token);
					sbM.AppendFormat(fmtStart, token);
					sbM.AppendFormat(fmtLineS, "offset", mat.mainTextureOffset);
					sbM.AppendFormat(fmtLineS, "scale", mat.mainTextureScale);
					sbM.AppendFormat(fmtLineS, "token", mat.name);
					sbM.AppendFormat(fmtLineS, "shader", mat.shader.name);
					// mat.shaderKeywords (string[]) // renderMap[mat.shader.name]
					foreach (var item in colorTags) {
						if (mat.HasProperty(item)) {
							try {
								Color col = mat.GetColor(item);
								var scol = String.Format(fmtColor, col.r, col.g, col.b, col.a); 
								sbM.AppendFormat(fmtLine, item, scol);
							} catch {
								sbM.AppendFormat(fmtLine, item, "<<Wrong Type>>");
							}
						}
					}
					foreach (var item in renderTags) {
						if (mat.HasProperty(item)) {
							try {
								sbM.AppendFormat(fmtLine, item, mat.GetFloat(item));
							} catch {
								sbM.AppendFormat(fmtLine, item, "<<Wrong Type>>");
							}
						}
					}
					
					sbM.Append(fmtEnd);
				}
				sbR.Append(fmtEndM);
				sbR.Append(fmtEnd);
			}
			sbR.Append(catEnd);
			sbM.Append(catEnd);

			// Build all together
			StringBuilder sbA = new StringBuilder();
			sbA.Append(docStart);
			sbA.AppendFormat(catStart, "meta");
			sbA.AppendFormat(fmtLineS, "name", fullname);
			sbA.Append(      catEnd);
			sbA.Append(sbR.ToString());
			sbA.Append(sbM.ToString());
			sbA.Append(docEnd);

			File.WriteAllText($@"C:\koikatsu_model\{prefix}.json", sbA.ToString());
		}

		
		static Regex regex = new Regex(@"^(ca_slot|ct_|p_cf_body)");
		internal static string FindParent(Transform _t) {
			Transform t = _t;
			string parent = "";

			while(t != null) {
				parent = t.name;
				if (regex.IsMatch(parent)) break;
				t = t.parent;
			}
			return parent;
		}

		internal static string GetName(UnityEngine.Object obj, string name, string parent) {
			string token = name;
			if (parent.StartsWith("ca_slot")) {
				token += "@" + parent;
			} else {
				token += "#" + obj.GetInstanceID();
			}
			return token;
		}
	}

	public class GeneratorGui {

		internal static ChaControl CurrentCharacter;

		internal static void Initialize() {
			MakerAPI.RegisterCustomSubCategories += RegisterCustomSubCategories;
			MakerAPI.ReloadCustomInterface += ReloadCustomInterface;
		}

		private static void RegisterCustomSubCategories(object sender, RegisterSubCategoriesEvent e) {
			
			var chara = MakerAPI.LastLoadedChaFile;
			// ChaShader._overtex1

			// Category to add our controls under. 
			//If you want to make a custom setting category/tab, use e.AddSubCategory
			MakerCategory category = MakerConstants.Parameter.Character;

			MakerButton foo = e.AddControl(new MakerButton("Generate JSON-Map", category, GeneratorPlugin.Instance));
			
			foo.OnClick.AddListener(() => {
				var name = CurrentCharacter.fileParam.fullname;
				var prefix = name + Math.Round((double)DateTime.Now.Ticks / 1000000);
				GeneratorMain.Generate(CurrentCharacter.gameObject, prefix, name);
			});
		}

		// KKAPI.Chara.CharaReloadEventArgs or KKAPI.Chara.CoordinateEventArgs
		private static void ReloadCustomInterface(object sender, object eventArgs) {
			if (eventArgs is KKAPI.Chara.CoordinateEventArgs coordArgs) {
				CurrentCharacter = coordArgs.Character;
			} else if (eventArgs is KKAPI.Chara.CharaReloadEventArgs chaReload) {
				CurrentCharacter = chaReload.ReloadedCharacter;
			}
		}
	}
}

