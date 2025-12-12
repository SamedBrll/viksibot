# config.py

import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_IDS = list(
    map(int, os.getenv("ADMIN_IDS", "").split(","))
)


ADMIN_USERNAMES = ["viskiletisim"]

# Kripto (USDT-TRC20) ayarları
CRYPTO_ADDRESS = "TVPCGL3SRMqeCSamFtL16TrjwxRewBtpr6"
CRYPTO_NETWORK = "TRC20"

# Havale / EFT
IBAN = "TR12 0011 1000 0000 0089 6442 00"
IBAN_NAME = "Eray Öz"

LIMITED_GROUPS = ["1", "2"]   # süreli olan gruplar
RENEW_PRICES = {
    "1": 700,   # 1. grubun yenileme fiyatı (TRY)
    "2": 500    # 2. grubun yenileme fiyatı (TRY)
}


# Gruplar (chat_id'leri ve davet linklerini sen dolduracaksın)
GROUPS = {
    "1": {
        "name": "💎YOUTUBE KATIL VİP💎 (1 AY)",
        "price_try": 1000,
        "chat_id": -1003320653631,      # gerçek chat_id ile değiştir
        "info": "🥃 VİSKİVİP YOUTUBE KATIL İÇERİKLER:\n\nYOUTUBE FENOMENLERİN PAHALI İÇERİKLERİNİ TEK KANALDA BİR ARAYA GETİRİYORUZ. KATIL VE ÖZEL İÇERİKLERİ HEPSİ ANINDA YÜKLENMEKTEDİR\n\nKATIL İÇERİK İSİMLERİ:Karolin Fişekçi, Zeynep Tümbek, Göksu Düldül, Jupiter, Gökce Ersoy, Buse's Life, Umut limanı, Sümmeye Korkmaz, Nur Turan, Naz Karalı, Zehra Karalı, Fatma İle Her Telden, Sinem Eligür, Emine Çoşkun, Aleyna Karakaş, Ebru Gezen, Ayşe Akdemir, Burcu Güven, Prenses Annesi Queen, Pamuk Şeker, Gözde'nin Kanalı, Zeynepjim, Ebru satan, Esra ile Hertelden, Talya Üstünel, Tuğba Gürel, Eda Nur Kılıç, İrem Kocaoğlu, Esmerella, Çiğdemle Hayat, Talya Burcu, Suynesli. Büşra Kahraman, Öykü Dürüsken Katıl\n\n❗️İsmi olmayan Youtube genel kategori üzerinden paylaşılmaktadır.",
        "photo": ["https://cdn.imgpile.com/f/hI2nht7.jpg" , "https://cdn.imgpile.com/f/KIB1jaO.jpg"]
    },
    "2": {
        "name": "💎SOSYAL MEDYA VİP💎 (1 AY)",
        "price_try": 500,
        "chat_id": -1002943071856,
        "info": "🥃VİSKİVİP SOSYAL MEDYA\n\nİNSTAGRAM-ONLYFANS-PATREON-TELEGRAM ÜCRETLİ ABONELİK ÖZEL İÇERİKLER\n\nİSİMLER; Miafitz, Elifkaraslan, Kader ÖZTÜRK, Mükemmel Nesli, Hanım Akdağ, Merve İbom, Ecrin Dilek Gökçe, Gamze Acet, Ece Ronay,Kardeniz Kılıç, Cheryboom, Ayşen, Suesalvia, Cerhawka, Ayça Çağan, İnci ve İlişkileri, Pelin Asmr, Yağmur Şimşek, Yazgülü, Avatar Kado, Nurcan Bingöl, Mürüvet Gül, Kübra Şentürk, Nisanur Yıldırım, Derinin Günlüğü, Aynur Çelikten, İpeklegeziyorum, Sarem Uysal, Kardelen Kardi, Dilan Ay, Sudemwah, Melek Özcagan, Simge Barankoğlu, Hazal Kılıç, Esra Rabia Ünal, İpek Bebek, Şeydanur Tunç\n\n❗️ İsmi olmayan genel kategori üzerinden paylaşılmaktadır.",
        "photo": ["https://cdn.imgpile.com/f/vdilkst.jpg","https://cdn.imgpile.com/f/xY4tJRl.jpg"]
    },
    "3": {
        "name": "💎BİGO/SNAPCHAT VİP💎 (SINIRSIZ)",
        "price_try": 500,
        "chat_id": -1003099753264,
        "info": "🥃 VİSKİ BİGO/SNAPCHAT/LİVU VİP\n\n 1-1 CANLI SOYUNDURMA VİDEOLARI VE DAHA FAZLASI...",
        "photo": ["https://cdn.imgpile.com/f/VFr69BK.jpg","https://cdn.imgpile.com/f/fPKh0qU.jpg"]
    },
    "4": {
        "name": "💎TURBANLI VİP💎 (SINIRSIZ)",
        "price_try": 500,
        "chat_id": -1002609391084,
        "info": "🥃 VİSKİ TÜRBANLI VİP\n\nTÜRBANLI ÇİFT,TANGO GİBİ YAYINLAR VEYA GİZLİ EŞLERİNİ ÇEKEN KOCALARIN VİDEOLARI VE DAHA FAZLASI...",
        "photo": ["https://cdn.imgpile.com/f/Ajaorl7.jpg","https://cdn.imgpile.com/f/eaCJpBB.jpg"]
    },
    "5": {
        "name": "💎GİZLİ ÇEKİM VİP💎 (SINIRSIZ)",
        "price_try": 500,
        "chat_id": -1002915184695,
        "info": "🥃VİSKİ GİZLİ ÇEKİM VİP\n\nKABİN,EŞİNİ,ANNESİNİ GİZLİ ÇEKİM VİDEOLARI VE DAHA FAZLASI...",
        "photo": ["https://cdn.imgpile.com/f/d2so4QU.jpg","https://cdn.imgpile.com/f/FB72gw6.jpg"]
    },
    "6": {
        "name": "💎TÜRK İ* CAM VİP💎 (SINIRSIZ)",
        "price_try": 500,
        "chat_id": -1003303764114,
        "info": "🥃VİSKİ VİP İ* CAM\n\n TÜRK İPCAM İÇERİKLER KARI-KOCA SEKS VİDEOLARI GİBİ DAHA FAZLASI...",
        "photo": ["https://cdn.imgpile.com/f/nZ4v8zY.jpg","https://cdn.imgpile.com/f/3vl8TsN.jpg"]
    },
    "7": {
        "name": "💎YABANCI İ* CAM VİP💎 (SINIRSIZ)",
        "price_try": 500,
        "chat_id": -1003396183683,
        "info": "🥃 VİSKİ VİP YABANCI *P CAM\n\n YABANCI İPCAM VİDEOLARI",
        "photo": ["https://cdn.imgpile.com/f/2A149Xz.jpg","https://cdn.imgpile.com/f/xLG4eM9.jpg"]
    },
    "8": {
        "name": "💎SOKAK VİP💎 (SINIRSIZ)",
        "price_try": 500,
        "chat_id": -1003416758426,
        "info": "🥃VİSKİ VİP SOKAK VİP\n\nSOKAKDA METRODA AVM GİZLİ ÇEKİLEN VİDEOLAR",
        "photo": ["https://cdn.imgpile.com/f/2A149Xz.jpg","https://cdn.imgpile.com/f/xLG4eM9.jpg"]
    },
    "9": {
        "name": "💎TÜRK İFSA💎 (SINIRSIZ)",
        "price_try": 500,
        "chat_id": -1003291672406,
        "info": "🥃VİSKİ TÜRK İFSA VİP\n\nPERİSCOPE,TANGO,SKYPE,OMEGLA, GİBİ İFSA VİDEOLARI VE DAHA FAZLASI",
        "photo": "https://cdn.imgpile.com/f/y2o20i4.png"
    },
    "10": {
        "name": "💎ETE* ALTI VİP💎 (SINIRSIZ)",
        "price_try": 200,
        "chat_id": -1003492432800,
        "info": "🥃VİSKİ VİP ET*K AL**\n\nELBİSE ETEK TÜRBANLI ETEK ALTI VİDEOLARI VE DAHA FAZLASI...",
        "photo": ["https://cdn.imgpile.com/f/SYq07s0.jpg","https://cdn.imgpile.com/f/K4VumDS.jpg"]
    },
}
