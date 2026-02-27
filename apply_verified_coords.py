#!/usr/bin/env python3
"""
Apply only the OSM-verified coordinate corrections that are < 3 km off.
Skips corrections > 3 km where Nominatim likely returned the wrong place
(West Bank settlements, Golan villages, and ambiguous Arab village names).

This script uses the captured output from the --apply run so no API calls needed.
"""
import re, os

html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

# (name, old_lat, old_lng, new_lat, new_lng) — only corrections < 3 km
PATCHES = [
    # 2.x km
    ("I'billin",          32.8056, 35.1658, 32.8209, 35.1913),
    ("Turan",             32.7956, 35.3506, 32.7773, 35.3725),
    ("Nahef",             32.9417, 35.2889, 32.9346, 35.3176),
    ("Pardesiya",         32.2958, 34.8867, 32.3070, 34.9098),
    ("Revivim",           31.0211, 34.7158, 31.0432, 34.7207),
    ("Sha'ar HaGolan",    32.7056, 35.6158, 32.6858, 35.6043),
    ("Majd al-Krum",      32.9167, 35.2333, 32.9226, 35.2580),
    ("Qiryat Tiv'on",     32.7217, 35.1267, 32.7332, 35.1453),
    ("Harish",            32.4553, 35.0298, 32.4596, 35.0511),
    ("Yesud HaMa'ala",    33.0697, 35.5869, 33.0574, 35.6030),
    ("Mi'ilya",           33.0122, 35.2494, 33.0281, 35.2583),
    # 1.x km
    ("Omer",              31.2581, 34.8363, 31.2678, 34.8513),
    ("Pardes Hanna",      32.4721, 34.9718, 32.4809, 34.9877),
    ("Kafr Qara",         32.5136, 35.0608, 32.5047, 35.0456),
    ("Yafi'a",            32.6717, 35.2808, 32.6866, 35.2772),
    ("Arad",              31.2589, 35.2128, 31.2600, 35.1951),
    ("Meona",             33.0021, 35.2620, 33.0167, 35.2597),
    ("Jerusalem",         31.7683, 35.2137, 31.7788, 35.2258),
    ("Deir Hanna",        32.8767, 35.3656, 32.8625, 35.3667),
    ("Mazkeret Batya",    31.8536, 34.8465, 31.8422, 34.8560),
    ("Yokneam",           32.6603, 35.1019, 32.6481, 35.0944),
    ("Mevaseret Zion",    31.8017, 35.1414, 31.8040, 35.1570),
    ("Beitar Illit",      31.6997, 35.1145, 31.6981, 35.0988),
    ("Eilon",             33.0753, 35.2208, 33.0633, 35.2197),
    ("Abu Snan",          32.9556, 35.1592, 32.9586, 35.1717),
    ("Degania Alef",      32.7024, 35.5644, 32.7085, 35.5749),
    ("Herzliya",          32.1663, 34.8433, 32.1677, 34.8308),
    ("Kfar Saba",         32.1742, 34.9077, 32.1802, 34.9181),
    ("Daliyat al-Karmel", 32.6935, 35.0607, 32.6922, 35.0483),
    ("Hod HaSharon",      32.1538, 34.8966, 32.1499, 34.8851),
    ("Ma'alot-Tarshiha",  33.0146, 35.2726, 33.0145, 35.2848),
    ("Kiryat Ata",        32.8134, 35.1094, 32.8042, 35.1041),
    ("Kfar Kama",         32.7253, 35.4506, 32.7211, 35.4408),
    ("Kiryat Bialik",     32.8286, 35.0845, 32.8367, 35.0893),
    ("Ein Gedi",          31.4608, 35.3887, 31.4524, 35.3848),
    ("Even Yehuda",       32.2637, 34.8884, 32.2725, 34.8868),
    ("Or Yehuda",         32.0334, 34.8558, 32.0270, 34.8630),
    ("Peki'in",           32.9758, 35.3236, 32.9772, 35.3340),
    ("Kfar Tavor",        32.6872, 35.4308, 32.6878, 35.4204),
    ("Jaljulia",          32.1572, 34.9622, 32.1523, 34.9537),
    ("Metula",            33.2777, 35.5700, 33.2692, 35.5723),
    ("Kfar Manda",        32.8197, 35.2619, 32.8114, 35.2598),
    ("Iksal",             32.6897, 35.3264, 32.6816, 35.3240),
    # 0.x km
    ("Rishon LeZion",     31.9642, 34.8007, 31.9636, 34.8101),
    ("Savyon",            32.0408, 34.8778, 32.0485, 34.8792),
    ("Nof HaGalil",       32.7086, 35.3236, 32.7023, 35.3183),
    ("Bat Yam",           32.0231, 34.7503, 32.0155, 34.7505),
    ("Migdal",            32.8361, 35.5078, 32.8387, 35.4994),
    ("Nazareth",          32.6996, 35.3035, 32.7046, 35.2972),
    ("Ashdod",            31.8014, 34.6436, 31.7957, 34.6489),
    ("Akko",              32.9267, 35.0840, 32.9282, 35.0756),
    ("Tel Mond",          32.2604, 34.9213, 32.2536, 34.9185),
    ("Binyamina",         32.5238, 34.9509, 32.5203, 34.9436),
    ("Katzrin",           32.9933, 35.6958, 32.9920, 35.6877),
    ("Yeroham",           30.9868, 34.9323, 30.9888, 34.9251),
    ("Lod",               31.9516, 34.8954, 31.9489, 34.8885),
    ("Kiryat Ekron",      31.8671, 34.8219, 31.8608, 34.8233),
    ("Birya",             32.9833, 35.4972, 32.9776, 35.5006),
    ("Reina",             32.7281, 35.3178, 32.7236, 35.3125),
    ("Beer Sheva",        31.2518, 34.7913, 31.2457, 34.7925),
    ("Ramat HaSharon",    32.1449, 34.8396, 32.1397, 34.8359),
    ("Ganei Tikva",       32.0628, 34.8827, 32.0604, 34.8761),
    ("Yehud",             32.0282, 34.8869, 32.0332, 34.8908),
    ("Kiryat Gat",        31.6073, 34.7647, 31.6094, 34.7712),
    ("Ofakim",            31.3179, 34.6228, 31.3126, 34.6209),
    ("Sde Boker",         30.8728, 34.7862, 30.8737, 34.7926),
    ("Fureidis",          32.6035, 34.9574, 32.5988, 34.9542),
    ("Safed",             32.9646, 35.4961, 32.9646, 35.5025),
    ("Isfiya",            32.7147, 35.0608, 32.7152, 35.0671),
    ("Daburiyya",         32.6878, 35.3697, 32.6928, 35.3716),
    ("Holon",             32.0158, 34.7799, 32.0160, 34.7860),
    ("Nazareth Illit",    32.7056, 35.3230, 32.7023, 35.3183),
    ("Karmiel",           32.9181, 35.2933, 32.9159, 35.2934),
    ("Tiberias",          32.7922, 35.5312, 32.7939, 35.5329),
    ("Majdal Shams",      33.2681, 35.7717, 33.2684, 35.7694),
    ("Kiryat Motzkin",    32.8372, 35.0808, 32.8391, 35.0804),
    ("Eilat",             29.5581, 34.9482, 29.5569, 34.9498),
    ("Givatayim",         32.0714, 34.8105, 32.0730, 34.8113),
    ("Kafr Qasim",        32.1138, 34.9743, 32.1152, 34.9753),
    ("Kafr Kanna",        32.7472, 35.3386, 32.7460, 35.3398),
    ("Mitzpe Ramon",      30.6104, 34.8014, 30.6120, 34.8012),
    ("Petah Tikva",       32.0878, 34.8878, 32.0878, 34.8860),
    ("Nahariya",          33.0078, 35.0942, 33.0063, 35.0946),
    ("Baqa al-Gharbiyye", 32.4185, 35.0437, 32.4197, 35.0428),
    ("Beit She'an",       32.4972, 35.4988, 32.4968, 35.4973),
    ("Maghar",            32.8858, 35.4047, 32.8858, 35.4062),
    ("Tamra",             32.8537, 35.1993, 32.8535, 35.1979),
    ("Kiryat Malachi",    31.7321, 34.7448, 31.7312, 34.7448),
    ("Nes Ziona",         31.9302, 34.7998, 31.9296, 34.7991),
    ("Ramat Gan",         32.0682, 34.8239, 32.0687, 34.8247),
    ("Umm al-Fahm",       32.5166, 35.1525, 32.5158, 35.1525),
    ("Rahat",             31.3929, 34.7540, 31.3934, 34.7547),
    ("Qalansawe",         32.2846, 34.9807, 32.2849, 34.9802),
    ("Netivot",           31.4218, 34.5883, 31.4214, 34.5884),
    ("Ein Bokek",         31.1975, 35.3600, 31.2014, 35.3639),
    ("Arrabe",            32.8533, 35.3344, 32.8486, 35.3358),
    ("Bnei Brak",         32.0828, 34.8338, 32.0874, 34.8324),
    ("Gedera",            31.8123, 34.7750, 31.8118, 34.7804),
    ("Lehavim",           31.3738, 34.8170, 31.3703, 34.8137),
    ("Rame",              32.9375, 35.3728, 32.9380, 35.3676),
    ("Kfar Shmaryahu",    32.1817, 34.8169, 32.1854, 34.8198),
    ("Hazor HaGlilit",    32.9778, 35.5483, 32.9792, 35.5433),
    ("Dimona",            31.0689, 35.0317, 31.0687, 35.0366),
    ("Nesher",            32.7729, 35.0420, 32.7709, 35.0381),
    ("Rosh Pinna",        32.9694, 35.5481, 32.9682, 35.5438),
    ("Afula",             32.6076, 35.2897, 32.6091, 35.2857),
    ("Hura",              31.3004, 34.9357, 31.2972, 34.9379),
    ("Kafr Yasif",        32.9497, 35.1665, 32.9533, 35.1657),
    ("Kiryat Ono",        32.0614, 34.8561, 32.0592, 34.8594),
    ("Kfar Yona",         32.3156, 34.9361, 32.3145, 34.9321),
    ("Shoham",            31.9983, 34.9433, 32.0005, 34.9465),
    ("Shlomi",            33.0781, 35.1519, 33.0761, 35.1486),
    ("Yavne",             31.8776, 34.7422, 31.8769, 34.7383),
    ("Rosh HaAyin",       32.0956, 34.9573, 32.0953, 34.9533),
    ("Atlit",             32.6957, 34.9422, 32.6928, 34.9402),
    ("Migdal HaEmek",     32.6747, 35.2381, 32.6766, 35.2413),
    ("Abu Ghosh",         31.8049, 35.1054, 31.8064, 35.1089),
    ("Ra'anana",          32.1845, 34.8711, 32.1860, 34.8678),
    ("Giv'at Shmuel",     32.0742, 34.8494, 32.0764, 34.8520),
    ("Latrun",            31.8374, 34.9847, 31.8361, 34.9878),
    ("Tirat Carmel",      32.7587, 34.9703, 32.7614, 34.9716),
    ("Elad",              32.0506, 34.9489, 32.0501, 34.9522),
    ("Sakhnin",           32.8665, 35.3018, 32.8638, 35.3023),
    ("Or Akiva",          32.5074, 34.9221, 32.5090, 34.9196),
    ("Rehovot",           31.8928, 34.8113, 31.8953, 34.8106),
    ("Gan Yavne",         31.7887, 34.7074, 31.7871, 34.7097),
    ("Jisr az-Zarqa",     32.5397, 34.9147, 32.5376, 34.9132),
    ("Tira",              32.2306, 34.9503, 32.2330, 34.9504),
    ("Zichron Ya'akov",   32.5703, 34.9556, 32.5712, 34.9530),
    ("Dimona",            31.0689, 35.0317, 31.0687, 35.0366),
]

def apply_fix(content, name, old_lat, old_lng, new_lat, new_lng):
    pattern = re.compile(
        r'(name:"' + re.escape(name) + r'",\s*lat:)' +
        re.escape(str(old_lat)) + r'(,\s*lng:)' + re.escape(str(old_lng))
    )
    new_content = pattern.sub(
        lambda m: m.group(1) + f'{new_lat:.4f}' + m.group(2) + f'{new_lng:.4f}',
        content, count=1
    )
    return new_content, new_content != content

with open(html_path, encoding="utf-8") as f:
    content = f.read()

patched = 0
skipped = 0
seen = set()

for name, old_lat, old_lng, new_lat, new_lng in PATCHES:
    if name in seen:
        continue
    seen.add(name)
    if old_lat == new_lat and old_lng == new_lng:
        skipped += 1
        continue
    content, changed = apply_fix(content, name, old_lat, old_lng, new_lat, new_lng)
    if changed:
        patched += 1
        print(f"  PATCHED  {name:<30} ({old_lat}, {old_lng}) → ({new_lat:.4f}, {new_lng:.4f})")
    else:
        print(f"  MISS     {name:<30} (pattern not found — already patched?)")

with open(html_path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"\nDone: {patched} patched, {skipped} no-ops (already matched).")
print("Skipped towns with > 3 km OSM delta (likely bad Nominatim matches):")
skipped_towns = [
    "Masade (175 km)", "Ariel (159 km)", "Givat Ze'ev (153 km)", "Julis (153 km)",
    "Oranit (69 km)", "Efrat (57 km)", "Kiryat Arba (24 km)", "Modi'in (23 km)",
    "Jericho (21 km)", "Mazra'a (17 km)", "Shfar'am (17 km)", "Tel Sheva (13 km)",
    "Hurfeish (11 km)", "Sajur (11 km)", "Yanuh-Jat (10 km)", "Zarzir (8.5 km)",
    "Sha'ab (8.5 km)", "Kisra-Sumei (8 km)", "Kfar Vradim (8 km)",
    "Ramot Naftali (7 km)", "Kochav Yair (7 km)", "Mitzpe Netofa (7 km)",
    "Kabul (7 km)", "Ma'ale Adumim (7 km)", "Zemer (6 km)", "Laqiya (5 km)",
    "Ilut (5 km)", "Tayibe (5 km)", "Mishmar HaNegev (4 km)", "Buq'ata (4 km)",
    "Yirka (4 km)", "Yavne'el (4 km)", "Neve Shalom (4 km)", "Rehasim (4 km)",
    "Tuba-Zangariyye (3 km)", "Ilabun (3 km)", "Kadima-Zoran (3 km)", "Netanya (3 km)",
]
for t in skipped_towns:
    print(f"  {t}")
