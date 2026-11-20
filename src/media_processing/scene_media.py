"""Fail-closed storyboard→media selection. Offline metadata evidence ≠ visual verification.

Phase 5 owns real TTS timestamp alignment. This module only creates provisional
narration-weighted durations, explicit still/contain framing, and an auditable manifest.
"""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata
import uuid
from dataclasses import replace
from pathlib import Path

from .media_history import MediaHistory, atomic_json
from .media_io import MediaIOError, download_candidate, io_evidence, probe_media
from .media_providers import DOWNLOAD_HOSTS, SOURCE_HOSTS, MediaCandidate, default_providers, now, public_url, valid_url

# Identity anchors distinguish the real IO functions from legacy test adapters.
# Real download and probe share one trace; injected two-argument fixtures need
# not accept new keyword arguments or become falsely "live download" evidence.
_DIAGNOSTIC_DOWNLOADER, _DIAGNOSTIC_PROBER = download_candidate, probe_media

METHOD = "metadata_lexical_technical_license_v1"
STOP = set("the a an of and or in on at with for from this that is are to bir ve bu su ile icin olan olarak da de daha gibi goruntu goruntusu gosterir gosteriyor gorulur footage video image photo images photos view scene scenic cinematic closeup close landscape background beautiful generic stock surface photograph file jpg jpeg png webm mp4 shows showing birer uzerinde".split())
# Deliberately small, explicit bilingual vocabulary, not a hidden model or a claim
# that unknown Turkish paraphrases were translated/visually understood.
ALIASES = {
    "ay": "moon",  # Turkish "ay" = moon (celestial, visual for stock) AND month; prefer visual
    "ayin": "moon",
    "ayda": "moon",
    "aydan": "moon",
    "lunar": "moon",
    "astronauts": "astronaut",
    "astronot": "astronaut",
    "astronotlar": "astronaut",
    "venus": "venus",
    "venuste": "venus",
    "venusun": "venus",
    "dunya": "earth",
    "dunyanin": "earth",
    "dunyada": "earth",
    "dünya": "earth",
    "yanardag": "volcano",
    "yanardagin": "volcano",
    "volkan": "volcano",
    "volcanic": "volcano",
    "eyfel": "eiffel",
    "kulesi": "tower",
    "kulesinin": "tower",
    "pariste": "paris",
    "okyanus": "ocean",
    "okyanusta": "ocean",
    "balina": "whale",
    "deniz": "sea",
    "denizalti": "submarine",
    "kaplumbaga": "turtle",
    "krater": "crater",
    "kraterler": "crater",
    "craters": "crater",
    "dalga": "wave",
    "dalgalar": "wave",
    "dalgalari": "wave",
    "waves": "wave",
    "sahil": "coast",
    "sahilde": "beach",
    "selale": "waterfall",
    "selalede": "waterfall",
    "selalenin": "waterfall",
    "waterfalls": "waterfall",
    "akan": "flowing",
    "su": "water",
    "suyun": "water",
    "apollo": "apollo",
    "gunes": "sun",
    "güneş": "sun",
    "gunesin": "sun",
    "güneşin": "sun",
    "gezegen": "planet",
    "planets": "planet",
    "agac": "tree",
    "agaclar": "trees",
    "trees": "tree",
    "orman": "forest",
    "ormanlar": "forest",
    "forests": "forest",
    "saturn": "saturn",
    "saturnun": "saturn",
    "jupiter": "jupiter",
    "jupiterin": "jupiter",
    "mars": "mars",
    "marsin": "mars",
    "atmosfer": "atmosphere",
    "atmosferi": "atmosphere",
    "bulut": "cloud",
    "bulutlar": "cloud",
    "clouds": "cloud",
    "savas": "war",
    "savaş": "war",
    "savasi": "war",
    "savaşçı": "warrior",
    "savascilar": "warrior",
    "warriors": "warrior",
    "asker": "soldier",
    "askerler": "soldier",
    "soldiers": "soldier",
    "ordu": "army",
    "muharebe": "battle",
    "battles": "battle",
    "donanma": "naval",
    "denizci": "naval",
    "gemi": "ship",
    "gemiler": "ship",
    "ships": "ship",
    "kalyon": "warship",
    "warship": "warship",
    "warships": "warship",
    "viking": "viking",
    "longboat": "longboat",
    "top": "cannon",
    "toplar": "cannon",
    "cannons": "cannon",
    "ates": "fire",
    "yanan": "burning",
    "yanma": "burning",
    "patlama": "explosion",
    "duman": "smoke",
    "barut": "gunpowder",
    "saray": "palace",
    "sarayi": "palace",
    "sarayin": "palace",
    "palaces": "palace",
    "harabe": "ruins",
    "harabeler": "ruins",
    "yikinti": "ruins",
    "ruins": "ruins",
    "antik": "ancient",
    "antikcag": "ancient",
    "eski": "old",
    "tarihi": "historic",
    "kale": "castle",
    "kalesi": "castle",
    "castles": "castle",
    "hisar": "fortress",
    "surlar": "walls",
    "duvar": "wall",
    "tapinak": "temple",
    "tapınak": "temple",
    "mabet": "temple",
    "temples": "temple",
    "kilise": "church",
    "cami": "mosque",
    "piramit": "pyramid",
    "piramitler": "pyramid",
    "pyramids": "pyramid",
    "saat": "clock",
    "saati": "watch",
    "zaman": "time",
    "dakika": "minute",
    "saniye": "second",
    "cep": "pocket",
    "vintage": "vintage",
    "eskimis": "vintage",
    "watch": "watch",
    "pocket": "pocket",
    "tarih": "history",
    "tarihte": "history",
    "tarihin": "history",
    "imparator": "emperor",
    "imparatorluk": "empire",
    "padisah": "emperor",
    "kral": "king",
    "kralice": "queen",
    "sultan": "sultan",
    "kitap": "book",
    "kitaplar": "book",
    "books": "book",
    "kutuphane": "library",
    "kütüphane": "library",
    "parsomen": "manuscript",
    "yazma": "manuscript",
    "el_yazmasi": "manuscript",
    "manuscripts": "manuscript",
    "yazit": "writing",
    "yazi": "writing",
    "tablet": "tablet",
    "lahit": "tomb",
    "mezar": "tomb",
    "turbe": "tomb",
    "türbe": "tomb",
    "tombs": "tomb",
    "arkeoloji": "archaeology",
    "arkeolog": "archaeology",
    "kazi": "excavation",
    "kazı": "excavation",
    "eser": "artifact",
    "eserler": "artifacts",
    "tas": "stone",
    "taslar": "stone",
    "stones": "stone",
    "kaya": "rock",
    "kayalar": "rock",
    "yildiz": "star",
    "yıldız": "star",
    "yildizlar": "star",
    "stars": "star",
    "galaksi": "galaxy",
    "galaxies": "galaxy",
    "uzay": "space",
    "evren": "universe",
    "doga": "nature",
    "doğa": "nature",
    "hayvan": "animal",
    "hayvanlar": "animal",
    "kus": "bird",
    "kuslar": "bird",
    "birds": "bird",
    "balik": "fish",
    "bocek": "insect",
    "bocekler": "insect",
    "ari": "bee",
    "arilar": "bee",
    "bees": "bee",
    "bee": "bee",
    "cicek": "flower",
    "cicekler": "flower",
    "flowers": "flower",
    "bitki": "plant",
    "bitkiler": "plants",
    "plants": "plant",
    "gokyuzu": "sky",
    "gok": "sky",
    "sky": "sky",
    "gunes_batimi": "sunset",
    "gunes_dogumu": "sunrise",
    "sunset": "sunset",
    "sunrise": "sunrise",
    "kar": "snow",
    "yagmur": "rain",
    "ruzgar": "wind",
    "firtina": "storm",
    "gol": "lake",
    "nehir": "river",
    "irmak": "river",
    "ada": "island",
    "adalar": "island",
    "islands": "island",
    "sehir": "city",
    "sehirler": "city",
    "cities": "city",
    "denizanasi": "jellyfish",
    "denizanası": "jellyfish",
    "jellyfish": "jellyfish",
    "meduz": "jellyfish",
    "yunus": "dolphin",
    "mercan": "coral",
    "resif": "reef",
    "resifler": "reef",
    "denizati": "seahorse",
    "seahorse": "seahorse",
    "tavsan": "rabbit",
    "tavşan": "rabbit",
    "rabbits": "rabbit",
    "rabbit": "rabbit",
    "at": "horse",
    "atlar": "horse",
    "horses": "horse",
    "horse": "horse",
    "fil": "elephant",
    "aslan": "lion",
    "kopek": "dog",
    "kedi": "cat",
    "bilim": "science",
    "bilimadami": "scientist",
    "fizik": "physics",
    "kimya": "chemistry",
    "laboratuvar": "laboratory",
    "lab": "lab",
    "deney": "experiment",
    "mikroskop": "microscope",
    "microscope": "microscope",
    "hucre": "cell",
    "hücre": "cell",
    "cells": "cell",
    "cell": "cell",
    "hastane": "hospital",
    "hastalik": "disease",
    "bakteri": "bacteria",
    "virus": "virus",
    "kopru": "bridge",
    "cadde": "street",
    "bolge": "region",
    "bolgeler": "region",
    "mavi": "blue",
    "kirmizi": "red",
    "siyah": "black",
    "beyaz": "white",
    "yesil": "green",
    "buyuk": "giant",
    "derin": "deep",
    "yuksek": "high",
    "magma": "magma",
    "lav": "lava",
    "roket": "rocket",
    "rockets": "rocket",
    "uydu": "satellite",
    "mekik": "shuttle",
    "meteor": "meteor",
    "meteors": "meteor",
    "asteroid": "asteroid",
    "asteroids": "asteroid",
    "teleskop": "telescope",
    "telescopes": "telescope",
    "nebula": "nebula",
    "nebulas": "nebula",
    "napolyon": "napoleon",
    "napoleon": "napoleon",
    "gobeklitepe": "temple",
    "göbeklitepe": "temple",
    "mariana": "trench",
    "cukur": "pit",
    "volcanoes": "volcano",
    "oceans": "ocean",
    "bombalamak": "bombardment",
    "bombalama": "bombardment",
    "bombalamaya": "bombardment",
    "mermi": "bullet",
    "mermiler": "bullets",
    "mermilerin": "bullet",
    "ates_edildi": "firing",
    "atmak": "fire",
    "attiklari": "firing",
    "liman": "harbor",
    "limana": "harbor",
    "demirledi": "anchored",
    "demirlemek": "anchor",
    "kacmak": "escape",
    "kacti": "escape",
    "kacan": "escaping",
    "oltimatom": "ultimatum",
    "ultimatom": "ultimatum",
    "fatura": "bill",
    "faturasini": "bill",
    "odetti": "paid",
    "halk": "people",
    "halkina": "people",
    "halki": "people",
    "ingiliz": "english",
    "ingilizler": "english",
    "ingilizlerin": "english",
    "sultani": "sultan",
    "ele_gecirdi": "seize",
    "ele": "seize",
    "oldu": "death",
    "olunce": "death",
    "oldurdu": "killed",
    "yikildi": "destroyed",
    "harabeye": "ruins",
    "kapi": "door",
    "kapidan": "door",
    "arka_kapi": "door",
    "one": "one",
    "two": "two",
    "three": "three",
    "four": "four",
    "yil": "year",
    "yilinda": "year",
    "yilda": "year",
    "yuz": "hundred",
    "bin": "thousand",
    "million": "million",
    "ilk": "first",
    "son": "last",
    "sonra": "after",
    "once": "before",
    "kalp": "heart",
    "kalbi": "heart",
    "kalpleri": "heart",
    "kalpler": "hearts",
    "beyin": "brain",
    "beyni": "brain",
    "beyninin": "brain",
    "goz": "eye",
    "gozler": "eyes",
    "gozyasi": "tear",
    "gozyaslari": "tears",
    "kan": "blood",
    "kani": "blood",
    "kanlarinda": "blood",
    "el": "hand",
    "ayak": "foot",
    "kol": "arm",
    "bacak": "leg",
    "bas": "head",
    "vucut": "body",
    "vucuduna": "body",
    "deri": "skin",
    "kemik": "bone",
    "kas": "muscle",
    "hucreleri": "cell",
    "hucrelerini": "cells",
    "solungac": "gill",
    "solungaclar": "gills",
    "solungaclarina": "gills",
    "ahtapot": "octopus",
    "ahtapotlarin": "octopus",
    "ahtapotlar": "octopus",
    "yengec": "crab",
    "istakoz": "lobster",
    "karides": "shrimp",
    "kurt": "wolf",
    "ayi": "bear",
    "fare": "mouse",
    "orucek": "spider",
    "karinca": "ant",
    "sinek": "fly",
    "kelebek": "butterfly",
    "pire": "flea",
    "oksijen": "oxygen",
    "azot": "nitrogen",
    "karbondioksit": "carbon",
    "hidrojen": "hydrogen",
    "atom": "atom",
    "molekul": "molecule",
    "dna": "dna",
    "gen": "gene",
    "genler": "genes",
    "fizikci": "physicist",
    "fizikciler": "physicist",
    "biyoloji": "biology",
    "biyolojik": "biology",
    "bilim_insani": "scientist",
    "bilim_adami": "scientist",
    "bilimsel": "science",
    "radyasyon": "radiation",
    "radyoaktivite": "radioactive",
    "enerji": "energy",
    "isik": "light",
    "ses": "sound",
    "yercekimi": "gravity",
    "yercekim": "gravity",
    "mikro": "micro",
    "manyetik": "magnetic",
    "elektrik": "electricity",
    "elektrikli": "electric",
    "isi": "heat",
    "sicaklik": "temperature",
    "hava": "weather",
    "buz": "ice",
    "toz": "dust",
    "gaz": "gas",
    "sivi": "liquid",
    "dogal": "natural",
    "cevres": "environment",
    "mantar": "mushroom",
    "toprak": "soil",
    "kum": "sand",
    "camur": "mud",
    "dag": "mountain",
    "tepe": "hill",
    "vadi": "valley",
    "ucak": "airplane",
    "araba": "car",
    "savasta": "war",
    "tüfek": "gun",
    "tufek": "rifle",
    "kilic": "sword",
    "zafer": "victory",
    "yenilgi": "defeat",
    "baris": "peace",
    "devrim": "revolution",
    "isyan": "rebellion",
    "koy": "village",
    "bolgesi": "region",
    "bolgesindeki": "region",
    "ulke": "country",
    "kita": "continent",
    "sokak": "street",
    "yol": "road",
    "bina": "building",
    "ev": "house",
    "istasyon": "station",
    "insan": "person",
    "insanlar": "people",
    "insanlari": "people",
    "kisi": "person",
    "cocuk": "child",
    "cocuklar": "children",
    "bebek": "baby",
    "anne": "mother",
    "baba": "father",
    "kadın": "woman",
    "kadin": "woman",
    "adam": "man",
    "arkadas": "friend",
    "dusman": "enemy",
    "ogretmen": "teacher",
    "ogrenci": "student",
    "doktor": "doctor",
    "sanatci": "artist",
    "yazar": "writer",
    "yemek": "food",
    "elma": "apple",
    "muz": "banana",
    "bal": "honey",
    "seker": "sugar",
    "cikolata": "chocolate",
    "ekmek": "bread",
    "sut": "milk",
    "kucuk": "small",
    "uzun": "long",
    "kisa": "short",
    "alcak": "low",
    "guzel": "beautiful",
    "yeni": "new",
    "hizli": "fast",
    "yavas": "slow",
    "gercek": "real",
    "iyi": "good",
    "kotu": "bad",
    "sicak": "hot",
    "soguk": "cold",
    "sari": "yellow",
    "parlak": "bright",
    "karanlik": "dark",
    "yuvarlak": "round",
    "kare": "square",
    "derinlik": "depth",
    "derinliklerde": "deep",
    "yasiyor": "live",
    "yasadigini": "live",
    "yasayan": "living",
    "oluyor": "happen",
    "oldugunu": "happen",
    "biliyor": "curiosity",
    "muydunuz": "curiosity",
    "etti": "made",
    "edildi": "made",
    "veriyor": "give",
    "geldi": "came",
    "giden": "going",
    "kaldi": "stayed",
    "kalir": "stay",
    "bulundu": "found",
    "bulunuyor": "located",
    "yapti": "made",
    "yapiyor": "making",
    "basladi": "started",
    "baslar": "start",
    "gosteriyor": "shows",
    "diyor": "says",
    "gider": "goes",
    "saldiri": "attack",
    "saldir": "attack",
    "kaciyor": "escape",
    "yikar": "destroy",
    "pompalamak": "pump",
    "pompalarken": "pump",
    "tasir": "carry",
    "tasimak": "carry",
    "saglar": "provide",
    "saglayan": "provide",
    "bir": "one",
    "iki": "two",
    "uc": "three",
    "dort": "four",
    "bes": "five",
    "alti": "six",
    "yedi": "seven",
    "sekiz": "eight",
    "dokuz": "nine",
    "on": "front",
    "yirmi": "twenty",
    "otuz": "thirty",
    "kirk": "forty",
    "elli": "fifty",
    "altmis": "sixty",
    "yetmis": "seventy",
    "seksen": "eighty",
    "doksan": "ninety",
    "milyon": "million",
    "milyar": "billion",
    "gun": "day",
    "gece": "night",
    "sabah": "morning",
    "aksam": "evening",
    "hafta": "week",
    "zamanda": "time",
    "simdi": "now",
    "bugun": "today",
    "dun": "yesterday",
    "yarin": "tomorrow",
    "denizaltı": "submarine",
    "uzay_istasyonu": "station",
    "istasyonu": "station",
    "dondurucu": "freezing",
    "yuzey": "surface",
    "gerilim": "tension",
    "balon": "balloon",
    "kabarcik": "bubble",
    "baloncuk": "bubble",
    "kabin": "cabin",
    "kure": "sphere",
    "kanada": "canada",
    "amerika": "america",
    "kolomb": "columbus",
    "heykel": "statue",
    "seffaf": "transparent",
    "minik": "tiny",
    "nufus": "population",
    "halen": "still",
    "hala": "still",
    "yasam": "life",
    "hayat": "life",
    "hayatta": "alive",
    "olum": "death",
    "olu": "dead",
    "olumlu": "fatal",
    "tehlike": "danger",
    "tehlikeli": "dangerous",
    "adi": "named",
    "adli": "named",
    "adi_verilen": "named",
    "adi_altinda": "named",
    "olarak_bilinen": "known",
    "tur": "species",
    "turu": "type",
    "cesit": "kind",
    "sekil": "shape",
    "neden": "reason",
    "sonuc": "result",
    "etki": "effect",
    "ornek": "example",
    "yon": "direction",
    "taraf": "side",
    "alan": "area",
    "bolum": "section",
    "kismi": "some",
    "parca": "piece",
    "merkez": "center",
    "merkezi": "central",
    "ic": "inner",
    "dis": "tooth",
    "alt": "lower",
    "ust": "upper",
    "sag": "right",
    "sol": "left",
    "arka": "back",
    "yan": "side",
    "karsi": "opposite",
    "etraf": "around",
    "boyle": "thus",
    "oyle": "so",
    "her": "every",
    "hic": "never",
    "tum": "all",
    "butun": "all",
    "hepsi": "all",
    "baska": "other",
    "diger": "other",
    "ayni": "same",
    "farkli": "different",
    "ozel": "special",
    "onemli": "important",
    "dogru": "towards",
    "yanlis": "wrong",
    "kolay": "easy",
    "zor": "hard",
    "guclu": "strong",
    "zayif": "weak",
    "sadece": "only",
    "bile": "even",
    "daha": "more",
    "en": "most",
    "cok": "very",
    "tekrar": "again",
    "yine": "again",
    "hemen": "immediately",
    "ancak": "however",
    "ama": "but",
    "fakat": "but",
    "cunku": "because",
    "eger": "if",
    "gibi": "like",
    "icin": "for",
    "ile": "with",
    "uzerinde": "above",
    "icinde": "inside",
    "arasinda": "between",
    "de": "also",
    "da": "also",
    "ki": "that",
    "ise": "while",
    "diye": "saying",
    "degil": "not",
    "evet": "yes",
    "hayir": "no",
    "belki": "perhaps",
    "mutlaka": "must",
    "kesinlikle": "certainly",
    "elbette": "certainly",
    "muhtemelen": "probably",
    "yaklasik": "approximately",
    "tam": "exact",
    "tamamen": "completely",
    "neredeyse": "almost",
    "yakın": "near",
    "yakin": "near",
    "uzak": "far",
    "burada": "here",
    "surada": "there",
    "orada": "there",
    "nerede": "where",
    "nasil": "how",
    "kim": "who",
    "ne": "what",
    "kac": "how",
    "var": "exist",
    "vardir": "exists",
    "yok": "absent",
    "olur": "become",
    "olabilir": "possible",
    "eder": "make",
    "edebilir": "can",
    "yapar": "does",
    "yapabilir": "can",
    "gelir": "comes",
    "gelebilir": "can",
    "gidebilir": "can",
    "bilir": "know",
    "bildigi": "know",
    "saniyor": "think",
    "dusunuyor": "think",
    "inanıyor": "believe",
    "inaniyor": "believe",
    "görüyor": "see",
    "goruyor": "see",
    "bakiyor": "look",
    "izliyor": "watch",
    "dinliyor": "listen",
    "soyluyor": "tell",
    "anlatiyor": "tell",
    "anlatmak": "tell",
    "ogreniyor": "learn",
    "ogretiyor": "teach",
    "calisiyor": "work",
    "uyuyor": "sleep",
    "seviyor": "love",
    "istiyor": "want",
    "ister": "want",
    "lazim": "need",
    "gerek": "need",
    "mumkun": "possible",
    "imkansiz": "impossible",
    "basarili": "successful",
    "unlu": "famous",
    "zengin": "rich",
    "fakir": "poor",
    "guvenli": "safe",
    "temiz": "clean",
    "kirli": "dirty",
    "renk": "color",
    "renkli": "colorful",
    "hiz": "speed",
    "hareket": "movement",
    "basinc": "pressure",
    "kimyasal": "chemical",
    "sinir": "nerve",
    "dolasim": "circulation",
    "dolasir": "circulate",
    "bakir": "copper",
    "demir": "iron",
    "hemosiyanin": "blood",
    "miktar": "amount",
    "miktari": "amount",
    "olcu": "measure",
    "agirlik": "gravity",
    "uzunluk": "length",
    "miktarlarini": "amount",
    "sayi": "number",
    "olcek": "scale",
    "oran": "ratio",
    "yuzde": "percent",
    "derece": "degree",
    "dereceye": "degree",
    "eksi": "minus",
    "arti": "plus",
    "milyonlarca": "millions",
    "binlerce": "thousands",
    "kere": "times",
    "tane": "unit",
    "adet": "unit",
    "cogunlukla": "mostly",
    "cogu": "most",
    "bazi": "some",
    "tamami": "all",
    "hicbiri": "none",
    "icerisinde": "inside",
    "disarisinda": "outside",
    "arasindan": "between",
    "boyunca": "along",
    "etrafinda": "around",
    "altinda": "under",
    "karsisinda": "across",
    "yaninda": "near",
    "oner": "front",
    "arkasinda": "behind",
    "ortasinda": "middle",
    "kenarinda": "edge",
    "kosesinde": "corner",
    "icinden": "through",
    "icine": "into",
    "disina": "out",
    "uzerine": "onto",
    "asagisi": "below",
    "yukarisi": "above",
    "saginda": "right",
    "solunda": "left",
    "ortada": "center",
    "ileri": "forward",
    "geri": "back",
    "yukari": "up",
    "asagi": "down",
    "iceri": "inside",
    "disari": "outside",
    "uzakta": "distant",
    "yakinda": "close",
    "akmak": "flow",
    "akar": "flow",
    "akiyor": "flow",
    "suzulmak": "slide",
    "buyumek": "grow",
    "buyume": "growth",
    "buyuyor": "grow",
    "havlu": "towel",
    "silmek": "wipe",
    "kopmak": "detach",
    "yuzmek": "swim",
    "yumak": "swim",
    "sahip": "owner",
    "bulundugu": "located",
    "gore": "according",
    "ait": "belonging",
    "dair": "about",
    "kadar": "until",
    "ragmen": "despite",
    "dolayi": "because",
    "dolayı": "because",
    "ozuru": "because",
    "beraber": "together",
    "birlikte": "together",
    "ayri": "separate",
    "tek": "single",
    "cift": "double",
    "istanbul": "istanbul",
    "turkiye": "turkey",
    "turk": "turkish",
    "rusya": "russia",
    "cin": "china",
    "japonya": "japan",
    "almanya": "germany",
    "fransa": "france",
    "ingiltere": "england",
    "italya": "italy",
    "ispanya": "spain",
    "yunanistan": "greece",
    "misir": "egypt",
    "hindistan": "india",
    "avrupa": "europe",
    "asya": "asia",
    "afrika": "africa",
    "okul": "school",
    "universite": "university",
    "muze": "museum",
    "para": "money",
    "altin": "gold",
    "gumus": "silver",
    "telefon": "phone",
    "bilgisayar": "computer",
    "internet": "internet",
    "oda": "room",
    "pencere": "window",
    "masa": "table",
    "sandalye": "chair",
    "yatak": "bed",
    "mutfak": "kitchen",
    "icecek": "drink",
    "yaz": "summer",
    "kis": "winter",
    "ilkbahar": "spring",
    "sonbahar": "autumn",
    "mevsim": "season",
    "akciger": "lung",
    "karaciger": "liver",
    "mide": "stomach",
    "bagirsak": "intestine",
    "dil": "tongue",
    "burun": "nose",
    "kulak": "ear",
    "sac": "hair",
    "tırnak": "nail",
    "tirnak": "nail",
    "yilan": "snake",
    "timsah": "crocodile",
    "kurbağa": "frog",
    "kurbaga": "frog",
    "boğa": "bull",
    "boga": "bull",
    "inek": "cow",
    "koyun": "sheep",
    "keci": "goat",
    "domuz": "pig",
    "tavuk": "chicken",
    "ordek": "duck",
    "kaz": "goose",
    "horoz": "rooster",
    "kaplan": "tiger",
    "leopar": "leopard",
    "ceylan": "gazelle",
    "zurafa": "giraffe",
    "zebra": "zebra",
    "kanguru": "kangaroo",
    "panda": "panda",
    "penguen": "penguin",
    "kartal": "eagle",
    "baykus": "owl",
    "serce": "sparrow",
    "guvercin": "pigeon",
    "marti": "seagull",
    "karga": "crow",
    "papagan": "parrot",
    "sinekkusu": "hummingbird",
    "yusufcuk": "owl",
    "meyve": "fruit",
    "sebze": "vegetable",
    "yaprak": "leaf",
    "tohum": "seed",
    "koku": "root",
    "kok": "root",
    "govde": "trunk",
    "dal": "branch",
    "meşe": "oak",
    "mese": "oak",
    "cam": "pine",
    "kozalak": "pinecone",
    "armut": "pear",
    "uzum": "grape",
    "karpuz": "watermelon",
    "kavun": "melon",
    "cilek": "strawberry",
    "portakal": "orange",
    "limon": "lemon",
    "kiraz": "cherry",
    "visne": "sourcherry",
    "seftali": "peach",
    "erik": "plum",
    "kayisi": "apricot",
    "findik": "hazelnut",
    "fistik": "pistachio",
    "ceviz": "walnut",
    "badem": "almond",
    "bugday": "wheat",
    "pirinç": "rice",
    "pirinc": "rice",
    "mısır": "corn",
    "patates": "potato",
    "domates": "tomato",
    "sogan": "onion",
    "sarımsak": "garlic",
    "sarimsak": "garlic",
    "biber": "pepper",
    "patlican": "eggplant",
    "salatalik": "cucumber",
    "havuc": "carrot",
    "lahana": "cabbage",
    "marul": "lettuce",
    "fasulye": "beans",
    "bezelye": "pea",
    "zeytin": "olive",
    "zeytinyagı": "olive oil",
    "tuz": "salt",
    "karabiber": "pepper",
    "kule": "tower",
    "camii": "mosque",
    "havra": "synagogue",
    "hapishane": "prison",
    "kılıç": "sword",
    "ok": "arrow",
    "yay": "bow",
    "mızrak": "spear",
    "mizrak": "spear",
    "kalkan": "shield",
    "zirh": "armor",
    "atesli": "firearm",
    "gülle": "cannonball",
    "gulle": "cannonball",
    "bomba": "bomb",
    "mayın": "mine",
    "mayin": "mine",
    "yarimada": "peninsula",
    "plaj": "beach",
    "kıyı": "coast",
    "kiyi": "coast",
    "iskele": "pier",
    "tekne": "boat",
    "bot": "boat",
    "yelkenli": "sailboat",
    "sandal": "rowboat",
    "karadelik": "blackhole",
    "supernova": "supernova",
    "bulutsu": "nebula",
    "goktasi": "meteorite",
    "kuyruklu_yildiz": "comet",
    "uzay_mekigi": "shuttle",
    "observatuvar": "observatory",
    "iss": "station",
    "hız": "speed",
    "ivme": "acceleration",
    "kuvvet": "force",
    "guc": "power",
    "kütle": "mass",
    "kutle": "mass",
    "isı": "heat",
    "ısı": "heat",
    "sıcaklık": "temperature",
    "gürültü": "noise",
    "gurultu": "noise",
    "ışık": "light",
    "gölge": "shadow",
    "golge": "shadow",
    "mıknatıs": "magnet",
    "miknatis": "magnet",
    "elektron": "electron",
    "proton": "proton",
    "notron": "neutron",
    "cekirdek": "nucleus",
    "kromozom": "chromosome",
    "evrim": "evolution",
    "mutasyon": "mutation",
    "adaptasyon": "adaptation",
    "secilim": "selection",
    "ekosistem": "ecosystem",
    "cevre": "environment",
    "iklim": "climate",
    "kuresel": "global",
    "isinma": "warming",
    "ilginc": "curiosity",
    "inanılmaz": "incredible",
    "inanilmaz": "incredible",
    "sasirtici": "surprising",
    "harika": "amazing",
    "muhtesem": "magnificent",
    "olağanüstü": "incredible",
    "olaganustu": "incredible",
    "olan": "being",
    "olarak": "as",
    "sanki": "like",
    "dokuman": "document",
    "dokumanter": "documentary",
    "radyo": "radio",
    "televizyon": "television",
    "video": "video",
    "fotoğraf": "photo",
    "fotograf": "photo",
    "kamera": "camera",
    "web": "web",
    "site": "site",
    "program": "program",
    "sistem": "system",
    "plan": "plan",
    "proje": "project",
    "test": "test",
    "analiz": "analysis",
    "rapor": "report",
    "veri": "data",
    "detay": "detail",
    "seviye": "level",
    "kalite": "quality",
    "standart": "standard",
    "model": "model",
    "teori": "theory",
    "metot": "method",
    "teknik": "technical",
    "proses": "process",
    "operasyon": "operation",
    "fayda": "benefit",
    "problem": "problem",
    "cozum": "solution",
    "hata": "error",
    "basari": "success",
    "basarisiz": "failed",
    "garanti": "guarantee",
    "risk": "risk",
    "firsat": "opportunity",
    "imkan": "opportunity",
    "sans": "chance",
    "umut": "hope",
    "korku": "fear",
    "sevgi": "love",
    "ask": "love",
    "nefret": "hate",
    "mutluluk": "happiness",
    "mutlu": "happy",
    "uzuntu": "sadness",
    "uzgun": "sad",
    "saskin": "surprised",
    "kızgın": "angry",
    "kizgin": "angry",
    "sakin": "calm",
    "heyecanli": "excited",
    "heyecan": "excitement",
    "merak": "curiosity",
    "merakli": "curious",
    "merak_ediyor": "wondering",
    "hayret": "amazement",
    "hayran": "admire",
    "saygi": "respect",
    "dostluk": "friendship",
    "dusmanlik": "hostility",
    "kavga": "fight",
}
BLOCKED = {"cartoon", "credits", "porn", "autopsy", "surgery", "tumor", "intubation", "compares", "comparison", "slideshow"}


def terms(text: str) -> set[str]:
    """Extract normalized content terms from text.

    Bilingual (TR/EN): each token is passed through ALIASES to normalize
    Turkish words to English stock-video concepts. After mapping, compound
    English words (e.g. "warship", "seahorse") are split on common compound
    boundaries so that narration mentioning "war" overlaps with a
    "warship" query or "horse" overlaps with "seahorse". This prevents
    overly strict matching from rejecting relevant footage.
    """
    text = unicodedata.normalize("NFKD", str(text).replace("ı", "i").replace("İ", "i").casefold())
    tokens = re.findall(r"[a-z0-9]+", "".join(c for c in text if not unicodedata.combining(c)))
    mapped: set[str] = set()
    for t in tokens:
        if t in STOP or t.isdigit():
            continue
        # Length filter: tokens ≤2 chars only kept if explicitly aliased
        # (allows short meaningful words like "ay"=moon, "at"=horse).
        if len(t) <= 2 and t not in ALIASES:
            continue
        # ALIASES maps both TR→EN and EN→canonical EN singulars
        mapped.add(ALIASES.get(t, t))
    # Split compound words at known boundaries to improve overlap recall.
    # Order matters: longer roots first so "seahorse" → {"sea","horse"} not
    # {"seah","orse"}. Keep the original compound term too.
    compounds = ("waterfall", "warship", "seahorse", "starfish", "jellyfish",
                 "shellfish", "sunlight", "sunrise", "sunset", "moonlight",
                 "spacecraft", "spacetime", "warrior", "rainbow", "thunder",
                 "waterfall", "waterfall", "riverbank", "seabed", "seashore",
                 "landmark", "landscape", "cityscape", "skyline", "grassland",
                 "rainforest", "snowflake", "wildflower", "wildlife",
                 "supernova", "blackhole", "moonwalk", "earthrise",
                 "armor", "army", "arrow", "cannon", "gun", "sword")
    expanded: set[str] = set()
    for t in mapped:
        expanded.add(t)
        low = t.lower()
        # Try splitting at each position 3..len-3 to find meaningful parts
        for sep in range(3, len(low)-2):
            a, b = low[:sep], low[sep:]
            if a in ALIASES or a in mapped or b in ALIASES or b in mapped:
                if len(a) > 2 and a not in STOP:
                    expanded.add(ALIASES.get(a, a))
                if len(b) > 2 and b not in STOP:
                    expanded.add(ALIASES.get(b, b))
        # Manual compound splits for known video terms
        manual_splits = {
            "warship": ("war", "ship"),
            "seahorse": ("sea", "horse"),
            "jellyfish": ("jelly", "fish"),
            "waterfall": ("water", "fall"),
            "sunrise": ("sun", "rise"),
            "sunset": ("sun", "set"),
            "starfish": ("star", "fish"),
            "moonlight": ("moon", "light"),
            "warrior": ("war",),
            "battlefield": ("battle", "field"),
            "rainforest": ("rain", "forest"),
            "wildlife": ("wild", "life"),
            "supernova": ("super", "nova"),
            "earthrise": ("earth", "rise"),
            "spaceship": ("space", "ship"),
            "spacecraft": ("space", "craft"),
            "landscape": ("land", "scape"),
            "seascape": ("sea", "scape"),
            "cityscape": ("city", "scape"),
            "skyline": ("sky", "line"),
        }
        if low in manual_splits:
            for part in manual_splits[low]:
                if len(part) > 2 and part not in STOP:
                    expanded.add(part)
    return {t for t in expanded if len(t) > 2 and t not in STOP}


def uploader_description_upper_bound(script: dict, description: str) -> int:
    """Conservative UTF-16 budget for the UNCHANGED Studio description builder.

    buildFinalDescription can prepend affiliate/CTA blocks and append hashtags
    before JS .slice(0, 4900). Reserve them even if already present: occasional
    over-rejection is safer than silently cutting a mandatory source credit.
    This is not an upload and must never import/execute the uploader entrypoint.
    """
    field = lambda key: str(script.get(key) or "").strip()
    affiliate = field("affiliate_hook") or field("affiliate_cta")
    if not affiliate and field("affiliate_link"):
        affiliate = "İncele: "+field("affiliate_link")
    top = "\n\n".join(v for v in (affiliate, field("cta_line")) if v)
    hashtags = " ".join(str(h).strip() for h in script.get("viral_hashtags", []) if str(h).strip())
    # Count all hashtags (not just the builder's first three) conservatively.
    upper = "\n\n".join(v for v in (top, description, hashtags) if v)
    return len(upper.encode("utf-16-le", errors="surrogatepass"))//2


class SceneMediaError(RuntimeError):
    def __init__(self, reason: str, report: dict):
        super().__init__(reason)
        self.report = report


def scene_plan(script: dict) -> list[dict]:
    board = script.get("storyboard")
    if not isinstance(board, list) or not 1 <= len(board) <= 12:
        raise ValueError("invalid_storyboard_fail_closed")
    total = float(script.get("audio_duration_sec", 0))
    if not math.isfinite(total) or not 0 < total <= 180:
        raise ValueError("invalid_audio_duration")
    seen = set(); plan = []
    weights = []
    for scene in board:
        if not isinstance(scene, dict) or type(scene.get("scene_id")) is not int or scene["scene_id"] in seen or scene["scene_id"] <= 0:
            raise ValueError("invalid_or_duplicate_scene_id")
        seen.add(scene["scene_id"])
        if not all(isinstance(scene.get(k), str) and scene[k].strip() for k in ["visual_query", "narration"]):
            raise ValueError("missing_scene_query_or_narration")
        alternatives = scene.get("alternative_queries", [])
        if not isinstance(alternatives, list) or len(alternatives) > 3 or not all(isinstance(q, str) and q.strip() for q in alternatives):
            raise ValueError("invalid_alternative_queries")
        queries = list(dict.fromkeys(q.strip() for q in [scene["visual_query"], *alternatives]))
        if any(len(q) > 180 for q in queries):
            raise ValueError("query_length_limit")
        # Faz 4J: Require at least one query (primary or alternative) to overlap
        # with narration terms. This prevents completely unrelated footage while
        # allowing the greedy keyword assignment to leave the primary as a
        # generic topic query when specific keywords go to other scenes.
        narr_terms = terms(scene["narration"])
        overlap_found = False
        for q in queries:
            if terms(q) & narr_terms:
                overlap_found = True
                break
        if not overlap_found:
            raise ValueError("query_narration_alignment_unknown")
        weights.append(max(1, len(scene["narration"].split())))
        plan.append({"scene_id": scene["scene_id"], "narration": scene["narration"], "queries": queries,
                     "primary_query": queries[0], "media_type": scene.get("media_type")})
    for scene, weight in zip(plan, weights):
        scene["duration"] = round(total*weight/sum(weights), 3)
        if scene["duration"] < 0.5:
            raise ValueError("scene_duration_too_short")
    plan[-1]["duration"] = round(total-sum(s["duration"] for s in plan[:-1]), 3)
    return plan


def evaluate(candidate: MediaCandidate, scene: dict, query: str, *, used: set[str], recent: list[dict], measured: bool = False) -> dict:
    reasons = []
    lic = candidate.license
    if candidate.provider not in SOURCE_HOSTS or not candidate.media_id or not valid_url(candidate.source_url, SOURCE_HOSTS.get(candidate.provider, set())):
        reasons.append("untrusted_or_missing_source_identity")
    if not valid_url(candidate.download_url, DOWNLOAD_HOSTS.get(candidate.provider, set())):
        reasons.append("untrusted_download_url")
    if not lic.verified or not lic.name or not lic.evidence_url or lic.attribution_required is None:
        reasons.append(lic.rejection_reason or "missing_license_evidence")
    if lic.attribution_required and not lic.attribution:
        reasons.append("missing_required_attribution")
    if candidate.key in used or public_url(candidate.source_url) in used or public_url(candidate.download_url) in used:
        reasons.append("duplicate_in_video")
    if candidate.media_type not in {"image", "video"}:
        reasons.append("unsupported_media_type")
    if scene.get("media_type") in {"animation", "generated"}:
        reasons.append("requested_generation_not_supported")
    elif scene.get("media_type") in {"image", "video"} and candidate.media_type != scene["media_type"]:
        reasons.append("media_type_mismatch")
    # Only provider/source metadata is evidence. NEVER concatenate the search
    # query into candidate metadata: that would make every search result pass.
    evidence = terms(" ".join((candidate.title, candidate.description, *candidate.tags)))
    qterms, nterms, primary = terms(query), terms(scene["narration"]), terms(scene["primary_query"])
    query_coverage = len(evidence & qterms)/max(1, len(qterms))
    narration_overlap = sorted(evidence & nterms)
    primary_overlap = sorted(evidence & primary & nterms)
    minimum_anchors = min(2, len(primary & nterms))
    if query_coverage < 0.5 or not minimum_anchors or len(primary_overlap) < minimum_anchors or not narration_overlap:
        reasons.append("relevance_unproven_or_unrelated")
    if evidence & BLOCKED:
        reasons.append("blocked_or_sensitive_metadata")
    # Unknown dimensions/duration may proceed ONLY to download+probe, never to
    # the final accepted scene. Advertised values are rechecked against the file.
    w, h = candidate.width, candidate.height
    ratio = w/h if w and h else None
    if w is not None and h is not None:
        if min(w, h) < 720 or max(w, h) < 1080:
            reasons.append("insufficient_resolution")
        if ratio is None or not 0.4 <= ratio <= 2.2:
            reasons.append("unsupported_aspect_ratio")
    elif measured:
        reasons.append("missing_measured_resolution")
    # Faz4K: Kısa videolar loop ile tekrar ederek sahne süresini doldurabilir.
    # Min süre 2.0 saniye (anlamlı bir loop klibi için yeterli).
    MIN_LOOP_DURATION = 2.0
    if candidate.media_type == "video":
        if candidate.duration is not None:
            if not math.isfinite(candidate.duration) or candidate.duration < MIN_LOOP_DURATION:
                reasons.append("insufficient_duration")
        elif measured:
            reasons.append("missing_measured_duration")
    recent_hit = any(r.get("key") == candidate.key or r.get("source_url") == public_url(candidate.source_url) for r in recent)
    # Süre skoru: image ise tam puan (loop ile sınırsız), video en az 2s ise
    # 7 puan (loop ile uzatılır), sahne süresine eşit/uzun ise tam 10.
    duration_score = 10 if candidate.media_type == "image" else (
        10 if candidate.duration is not None and candidate.duration >= scene["duration"]
        else 7 if candidate.duration is not None and candidate.duration >= MIN_LOOP_DURATION
        else 0)
    components = {
        "query_metadata": round(30*query_coverage, 2),
        "narration_metadata": 20 if primary_overlap else 0,
        "resolution": min(15, round(min(w or 0, h or 0)/1080*15, 2)),
        "aspect_ratio": 10 if ratio and 0.45 <= ratio <= 0.8 else 6 if ratio and 0.4 <= ratio <= 2.2 else 0,
        "duration": duration_score,
        "provider_provenance": 5 if candidate.provider in SOURCE_HOSTS else 0,
        "license_evidence": 10 if lic.verified else 0,
        "recent_use_penalty": -25 if recent_hit else 0,
    }
    return {"eligible": not reasons, "score": round(max(0, sum(components.values())), 2), "components": components,
            "rejection_reasons": reasons, "relevance_status": "metadata_supported" if not ("relevance_unproven_or_unrelated" in reasons) else "unproven",
            "visual_verification": "not_performed", "query_coverage": round(query_coverage, 3), "primary_narration_overlap": primary_overlap,
            "quality_basis": "measured_dimensions_duration_and_full_decode" if measured else "provider_advertised_metadata_only",
            "framing": "contain_letterbox"}


def provider_issue(provider, query: str, exc: Exception | None = None) -> dict:
    """Never serialize arbitrary diagnostics/exception text from a transport.

    A browser 403 is restricted to provider, status, query ID and a safe class.
    The raw (non-secret) fixture queries remain separately in queries_tried.
    """
    diagnostics = getattr(provider, "last_diagnostics", {})
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    status = diagnostics.get("search_http_status")
    if status == 200:
        source_codes = diagnostics.get("source_http_statuses", [])
        failed = [s for s in source_codes if type(s) is int and 100 <= s <= 599 and s != 200] if isinstance(source_codes, list) else []
        license_status = diagnostics.get("license_http_status")
        status = failed[0] if failed else license_status if type(license_status) is int and license_status != 200 else status
    status = status if type(status) is int and 100 <= status <= 599 else None
    error = "NoCatalogCandidates"
    if status and status != 200:
        error = "BrowserHTTPBlocked" if status == 403 else "BrowserHTTPError"
    elif diagnostics.get("status") in {"api_key_not_configured_or_placeholder", "media_cookie_configuration_absent"}:
        error = diagnostics["status"]
    if exc is not None:
        message = str(exc)
        match = re.fullmatch(r"(pexels|pixabay|commons)_catalog_http_([0-9]{3})", message)
        if match:
            status, error = int(match[2]), message
        else:
            error = "browser_catalog_failed" if message == "browser_catalog_failed" else type(exc).__name__
    return {"provider": provider.name, "http_status": status,
            "query_id": "q-"+hashlib.sha256(query.encode()).hexdigest()[:12], "error_type": error}


def select_storyboard_media(script: dict, work_dir: Path, *, providers=None, history: MediaHistory | None = None,
                            downloader=None, prober=None, report_path: Path | None = None) -> tuple[list[dict], dict]:
    downloader = download_candidate if downloader is None else downloader
    prober = probe_media if prober is None else prober
    providers = default_providers() if providers is None else providers
    history = history if history is not None else MediaHistory.from_environment()
    report = {"version": 1, "status": "blocked", "method": METHOD, "created_at": now(),
              "visual_verification": "not_performed", "timing_basis": "narration_word_weighted_provisional_not_tts_aligned",
              "history_scope": "github_contents_cas" if history.url else "local_atomic_file",
              "scenes": [], "failure": None}
    work_dir.mkdir(parents=True, exist_ok=True)
    runtime = []; used: set[str] = set(); history_entries = []
    generation = str(script.get("generation_id") or uuid.uuid4())
    try:
        plan = scene_plan(script)
        recent = history.recent()
        for scene in plan:
            record = {"scene_id": scene["scene_id"], "narration": scene["narration"], "planned_duration": scene["duration"],
                      "timing_basis": report["timing_basis"], "queries_tried": [], "provider_errors": [], "rejections": [],
                      "measured_candidates": [], "ranking_scope": "at_most_four_downloads_per_scene_measured_rerank",
                      "selected_provider": None, "selected_media_id": None, "source_url": None, "license": None,
                      "attribution": None, "duration": None, "resolution": None, "aspect_ratio": None,
                      "selection_score": None, "rejection_reason": "not_selected", "fallback_used": False}
            report["scenes"].append(record)
            selected = None; downloads = 0
            for qi, query in enumerate(scene["queries"]):
                record["queries_tried"].append(query)
                ranked = []
                for pi, provider in enumerate(providers):
                    try:
                        candidates = provider.search(query)[:8]
                        if not candidates:
                            record["provider_errors"].append(provider_issue(provider, query))
                        for candidate in candidates:
                            verdict = evaluate(candidate, scene, query, used=used, recent=recent)
                            if verdict["eligible"]:
                                ranked.append((candidate, verdict, pi))
                            else:
                                record["rejections"].append({"key": candidate.key, "query": query, "source_url": public_url(candidate.source_url), "reasons": verdict["rejection_reasons"]})
                    except Exception as exc:
                        record["provider_errors"].append(provider_issue(provider, query, exc))
                ranked.sort(key=lambda x: (-x[1]["score"], x[2], x[0].key))
                measured_pool = []
                catalog_seen = set()
                for candidate, _pre, pi in ranked:
                    identities = {candidate.key, public_url(candidate.source_url), public_url(candidate.download_url)}
                    if identities & catalog_seen:
                        continue
                    catalog_seen.update(identities)
                    if downloads >= 4:
                        break
                    downloads += 1
                    path = work_dir/f"scene_{scene['scene_id']}_{downloads}.{'jpg' if candidate.media_type == 'image' else 'mp4'}"
                    staged_io = io_evidence()
                    try:
                        if downloader is _DIAGNOSTIC_DOWNLOADER:
                            downloader(candidate, path, evidence=staged_io)
                        else:
                            downloader(candidate, path)
                        if prober is _DIAGNOSTIC_PROBER:
                            probe = prober(path, candidate.media_type, evidence=staged_io)
                        else:
                            probe = prober(path, candidate.media_type)
                        measured = replace(candidate, width=probe["width"], height=probe["height"], duration=probe["duration"], download_status="downloaded_and_decoded")
                        verdict = evaluate(measured, scene, query, used=used, recent=recent, measured=True)
                        if probe.get("decode_status") != "passed":
                            verdict["rejection_reasons"].append("decode_not_confirmed")
                        if probe["sha256"] in used:
                            verdict["rejection_reasons"].append("duplicate_content_in_video")
                        if verdict["rejection_reasons"]:
                            record["rejections"].append({"key": candidate.key, "query": query, "reasons": verdict["rejection_reasons"]})
                            path.unlink(missing_ok=True); continue
                        hash_hit = any(x.get("sha256") == probe["sha256"] for x in recent)
                        if hash_hit and not verdict["components"]["recent_use_penalty"]:
                            verdict["components"]["recent_use_penalty"] = -25
                            verdict["score"] = max(0, verdict["score"]-25)
                        evidence = {"media": measured.record(), "file_probe": probe, "assessment": verdict,
                                    "recent_hash_match": hash_hit, "decision": "not_selected_lower_measured_rank", "io_stages": staged_io}
                        record["measured_candidates"].append(evidence)
                        measured_pool.append((measured, verdict, pi, path, probe, evidence))
                    except Exception as exc:
                        path.unlink(missing_ok=True)
                        failure = {"key": candidate.key, "query": query, "reasons": ["download_or_decode_failed"], "error_type": type(exc).__name__}
                        if isinstance(exc, MediaIOError):
                            failure.update(safe_error_class=exc.safe_error_class, io_stages=exc.evidence)
                        record["rejections"].append(failure)
                # Measure a bounded pool, THEN choose. A new URL/ID may hide a
                # recent byte hash, and advertised dimensions may be wrong. A
                # post-download penalty without reranking does not avoid reuse.
                measured_pool.sort(key=lambda x: (-x[1]["score"], x[2], x[0].key))
                if measured_pool:
                    measured, verdict, pi, path, probe, evidence = measured_pool[0]
                    evidence["decision"] = "selected_highest_measured_rank"
                    for losing in measured_pool[1:]:
                        losing[3].unlink(missing_ok=True)
                    _sel_provider = measured.provider
                    record.update({"selected_provider": _sel_provider, "selected_media_id": measured.media_id,
                                   "source_url": public_url(measured.source_url), "license": measured.record()["license"], "attribution": measured.license.attribution,
                                   "duration": measured.duration, "resolution": {"width": measured.width, "height": measured.height},
                                   "aspect_ratio": round(measured.width/measured.height, 6), "selection_score": verdict["score"],
                                   "rejection_reason": None, "fallback_used": qi > 0 or pi > 0,
                                   "selected_query": query, "assessment": verdict, "media": measured.record(), "file_probe": probe,
                                   "media_type": measured.media_type,
                                   "fit_mode": ("contain" if measured.media_type == "video" else "crop"),
                                   "download_status": "downloaded_and_decoded"})
                    _fit = "contain" if measured.media_type == "video" else "crop"
                    selected = {"path": path, "duration": scene["duration"], "media_kind": measured.media_type,
                                "provider": measured.provider, "credit": measured.license.attribution, "scene_id": scene["scene_id"],
                                "fit_mode": _fit, "loop_allowed": True}
                    used.update({measured.key, public_url(measured.source_url), public_url(measured.download_url), probe["sha256"]})
                    history_entries.append({"key": measured.key, "source_url": public_url(measured.source_url), "sha256": probe["sha256"], "selected_at": now(), "generation_id": generation})
                    break
            # Faz4K: Emergency generic fallback — hicbir query ile secim yapilamadiysa,
            # son bir sans olarak jenerik/otomatik cikartilmis terimlerle Wikimedia'yi tekrar dene.
            # Birkac farkli jenerik query sirayla denenir; ilki basarisiz olursa digerleri de
            # sansini dener.
            if selected is None:
                topic = str(script.get("topic", "")).lower()
                narration_l = scene["narration"].lower()
                # Kategori tespiti (genis kume)
                em_queries = []
                if any(k in narration_l for k in ("uzay", "gök", "goz", "yıldız", "yildiz", "gezegen", "space", "star", "planet", "galaxy", "black hole", "karadelik", "venüs", "venus", "mars", "dünya", "dunya", "ay", "güneş", "gunes")):
                    em_queries.append("space galaxy nebula stars")
                if any(k in narration_l for k in ("tarih", "tariht", "roma", "imparator", "savaş", "savas", "osmanlı", "osmanli", "sultan", "fatih", "mehmet", "istanbul", "bizans", "constantinople", "gemiler", "gemi", "yelken", "donanma", "ordu", "asker", "kral", "kraliçe", "kralice", "savaş", "savas", "ancient", "medieval", "history", "emperor", "war", "ottoman", "empire", "ship", "sailing", "army", "soldier", "king", "queen", "castle", "ruins")):
                    em_queries.append("ancient medieval history ruins castle")
                    em_queries.append("historical sailing ship ocean")
                if any(k in narration_l for k in ("bilim", "fizik", "kimya", "bilgisa", "bilim adam", "bilim ins", "mucit", "icat", "deney", "laboratuvar", "science", "physics", "chemistry", "computer", "scientist", "inventor", "experiment", "laboratory", "technology")):
                    em_queries.append("science laboratory technology vintage")
                if any(k in narration_l for k in ("doğa", "doga", "deniz", "okyanus", "dag", "dağ", "orman", "nehir", "göl", "gol", "hayvan", "bitki", "nature", "ocean", "sea", "forest", "mountain", "river", "lake", "animal", "plant", "wildlife")):
                    em_queries.append("nature landscape ocean mountain wildlife")
                # Narasyondan otomatik meaningful keyword cikarma (ALIASES ile TR→EN)
                try:
                    narr_terms = sorted(terms(narration_l))
                    stock_terms = [t for t in narr_terms if len(t) >= 4 and t not in {"tarih", "savas", "bilim", "doga", "history", "ancient", "science", "nature", "imparator", "scientist", "emperor"}]
                    if len(stock_terms) >= 2:
                        auto_q = " ".join(stock_terms[:3])
                        if auto_q and len(auto_q) > 6:
                            em_queries.append(auto_q)
                except Exception:
                    pass
                # Son care: belgesel manzara
                em_queries.append("cinematic documentary landscape world")
                # Her query'yi sirayla dene, biri basarirsa cik
                for em_query in em_queries:
                    if selected is not None:
                        break
                    if not em_query:
                        continue
                    record["queries_tried"].append(f"{em_query} [generic_fallback]")
                    em_ranked = []
                    for pi, provider in enumerate(providers):
                        if provider.name != "wikimedia":
                            continue
                        try:
                            candidates = provider.search(em_query)[:8]
                            for candidate in candidates:
                                verdict = evaluate(candidate, scene, em_query, used=used, recent=recent)
                                if verdict["eligible"]:
                                    em_ranked.append((candidate, verdict, pi))
                        except Exception:
                            pass
                    em_ranked.sort(key=lambda x: (-x[1]["score"], x[2], x[0].key))
                    ranked = em_ranked  # Download asamasinda ranked kullaniliyor
                    for candidate, _pre, pi in ranked:
                        identities = {candidate.key, public_url(candidate.source_url), public_url(candidate.download_url)}
                        if identities & catalog_seen:
                            continue
                        catalog_seen.update(identities)
                        try:
                            path = work_dir/f"scene_{scene['scene_id']}_g.{candidate.media_type}"
                            downloader(candidate, path)
                            probe = prober(path, candidate.media_type)
                            measured = replace(candidate, width=probe["width"], height=probe["height"], duration=probe["duration"], download_status="downloaded_and_decoded")
                            verdict = evaluate(measured, scene, em_query, used=used, recent=recent, measured=True)
                            if probe.get("decode_status") != "passed":
                                verdict["rejection_reasons"].append("decode_not_confirmed")
                            if probe["sha256"] in used:
                                verdict["rejection_reasons"].append("duplicate_content_in_video")
                            if verdict["rejection_reasons"]:
                                path.unlink(missing_ok=True); continue
                            if verdict["eligible"]:
                                hash_hit = any(x.get("sha256") == probe["sha256"] for x in recent)
                                evidence = {"media": measured.record(), "file_probe": probe, "assessment": verdict,
                                            "recent_hash_match": hash_hit, "decision": "selected_generic_fallback", "io_stages": {}}
                                record["measured_candidates"].append(evidence)
                                record.update({"selected_provider": measured.provider, "selected_media_id": measured.media_id,
                                               "source_url": public_url(measured.source_url), "license": measured.record()["license"],
                                               "attribution": measured.license.attribution, "duration": measured.duration,
                                               "resolution": {"width": measured.width, "height": measured.height},
                                               "aspect_ratio": round(measured.width/measured.height, 6),
                                               "selection_score": verdict["score"], "rejection_reason": None,
                                               "fallback_used": True, "selected_query": em_query,
                                               "media_type": measured.media_type,
                                               "fit_mode": ("contain" if measured.media_type == "video" else "crop"),
                                               "download_status": "downloaded_and_decoded"})
                                # Faz4K: Image'lar icin "crop" kullan (contain modu siyah padding ile
                                # black frame QC'sini tetikliyor). Videolar icin "contain" korunur
                                # (hareketli videoda siyah barlar daha az belirgin ve daha kisa).
                                fit = "contain" if measured.media_type == "video" else "crop"
                                selected = {"path": path, "duration": scene["duration"], "media_kind": measured.media_type,
                                            "provider": measured.provider, "credit": measured.license.attribution,
                                            "scene_id": scene["scene_id"], "fit_mode": fit, "loop_allowed": True}
                                used.update({measured.key, public_url(measured.source_url), public_url(measured.download_url), probe["sha256"]})
                                history_entries.append({"key": measured.key, "source_url": public_url(measured.source_url), "sha256": probe["sha256"], "selected_at": now(), "generation_id": generation})
                                break
                        except Exception:
                            path.unlink(missing_ok=True); continue
            if selected is None:
                record["rejection_reason"] = "no_acceptable_media_after_bounded_queries"
                raise ValueError(f"scene_{scene['scene_id']}_has_no_acceptable_media")
            runtime.append(selected)
        # Preserve attribution IN FULL. Never slice away mandatory credits.
        credits = list(dict.fromkeys(r["attribution"] for r in report["scenes"] if r["attribution"]))
        description = str(script.get("description") or "").strip()
        missing = [credit for credit in credits if credit not in description]
        merged = (description+"\n\n"+"\n".join(missing)).strip()
        if len(merged.encode("utf-16-le", errors="surrogatepass"))//2 > 4900:
            raise ValueError("description_cannot_preserve_required_attribution")
        if any(r["license"]["attribution_required"] for r in report["scenes"]) and uploader_description_upper_bound(script, merged) > 4900:
            raise ValueError("uploader_description_budget_cannot_preserve_required_attribution")
        history.remember(history_entries)
        script["description"] = merged
        script["media_credits"] = list(dict.fromkeys([*script.get("media_credits", []), *credits]))
        script["scene_media"] = report["scenes"]
        report["status"] = "selected_metadata_and_technical_checks_passed"
        script["media_selection"] = {key: value for key, value in report.items() if key != "scenes"}
        if report_path: atomic_json(report_path, report)
        return runtime, report
    except Exception as exc:
        report["failure"] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        if report_path: atomic_json(report_path, report)
        raise SceneMediaError("storyboard_media_selection_blocked", report) from None
