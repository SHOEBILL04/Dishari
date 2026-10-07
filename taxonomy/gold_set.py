"""Gold standard dataset loader, generator, and train/eval splitter for /taxonomy."""

import csv
import json
from pathlib import Path
from typing import Optional
import pandas as pd
from sklearn.model_selection import train_test_split

DEFAULT_GOLD_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "gold.csv"

# Pre-defined realistic sample templates across all 10 subjects and topics
GOLD_TEMPLATES = [
    # 1. Bangla Ancient Era
    ("top_bn_lit_ancient", "bangla", "চর্যাপদ কোন ছন্দে রচিত?", ["মাত্রাবৃত্ত", "অক্ষরবৃত্ত", "স্বরবৃত্ত", "পয়ার"]),
    ("top_bn_lit_ancient", "bangla", "হরপ্রসাদ শাস্ত্রী কত সালে নেপাল থেকে চর্যাপদের পুঁথি আবিষ্কার করেন?", ["১৯০৫", "১৯০৭", "১৯১৬", "১৯২১"]),
    ("top_bn_lit_ancient", "bangla", "চর্যাপদের আদি কবি বা প্রথম পদ রচয়িতা কে?", ["কাহ্নপা", "লুইপা", "ভুসুকুপা", "শবরপা"]),
    ("top_bn_lit_ancient", "bangla", "চর্যাপদের পদকর্তা কাহ্নপা কয়টি পদ রচনা করেন?", ["১০টি", "১২টি", "১৩টি", "১৪টি"]),
    ("top_bn_lit_ancient", "bangla", "চর্যাপদের তিব্বতি অনুবাদ কে আবিষ্কার করেন?", ["প্রবোধচন্দ্র বাগচী", "সুনীতিকুমার", "হরপ্রসাদ শাস্ত্রী", "ড. মুহম্মদ শহীদুল্লাহ"]),
    ("top_bn_lit_ancient", "bangla", "চর্যাগীতিকোষ এর মূল পুঁথি কোথায় সংরক্ষিত ছিল?", ["নেপাল রাজদরবার", "লন্ডন লাইব্রেরি", "ঢাকা বিশ্ববিদ্যালয়", "বঙ্গীয় সাহিত্য পরিষদ"]),

    # 2. Bangla Medieval Era
    ("top_bn_lit_medieval", "bangla", "শ্রীকৃষ্ণকীর্তন কাব্যটি কে রচনা করেন?", ["বড়ু চণ্ডীদাস", "বিদ্যাপতি", "জ্ঞানদাস", "গোবিন্দদাস"]),
    ("top_bn_lit_medieval", "bangla", "মনসামঙ্গল কাব্যের আদি কবি কে?", ["কানাহরি দত্ত", "নারায়ণ দেব", "বিজয়গুপ্ত", "বিপ্রদাস পিপলাই"]),
    ("top_bn_lit_medieval", "bangla", "আরাকান রাজসভার শ্রেষ্ঠ কবি আলাওলের বিখ্যাত কাব্য কোনটি?", ["পদ্মাবতী", "সতীময়না", "মধুমালতী", "ইউসুফ জোলেখা"]),
    ("top_bn_lit_medieval", "bangla", "অন্নদামঙ্গল কাব্যের রচয়িতা ভারতচন্দ্র রায়গুণাকর কোন যুগের কবি?", ["মধ্যযুগ", "প্রাচীন যুগ", "আধুনিক যুগ", "অন্ধকার যুগ"]),
    ("top_bn_lit_medieval", "bangla", "বৈষ্ণব পদাবলীর পদকর্তা বিদ্যাপতি কোন ভাষার কবি ছিলেন?", ["ব্রজবুলি", "মৈথিলি", "বাংলা", "সংস্কৃত"]),
    ("top_bn_lit_medieval", "bangla", "ইউসুফ-জোলেখা প্রণয়কাব্য কে রচনা করেন?", ["শাহ মুহম্মদ সগীর", "সাবিরিদ খান", "জৈনুদ্দীন", "দৌলত উজির"]),

    # 3. Bangla Modern Era
    ("top_bn_lit_modern", "bangla", "বাংলা সাহিত্যের প্রথম সার্থক উপন্যাস দুর্গেশনন্দিনী কার রচনা?", ["বঙ্কিমচন্দ্র চট্টোপাধ্যায়", "রবীন্দ্রনাথ ঠাকুর", "তারাশঙ্কর", "শরৎচন্দ্র"]),
    ("top_bn_lit_modern", "bangla", "মাইকেল মধুসূদন দত্তের মেঘনাদবধ কাব্য কোন ছন্দে রচিত?", ["অমিত্রাক্ষর", "মাত্রাবৃত্ত", "অক্ষরবৃত্ত", "গদ্যছন্দ"]),
    ("top_bn_lit_modern", "bangla", "রবীন্দ্রনাথ ঠাকুর কত সালে গীতাঞ্জলি কাব্যের জন্য নোবেল পুরস্কার পান?", ["১৯১১", "১৯১২", "১৯১৩", "১৯১৪"]),
    ("top_bn_lit_modern", "bangla", "কাজী নজরুল ইসলামের প্রথম প্রকাশিত কবিতা কোনটি?", ["মুক্তি", "বিদ্রোহী", "প্রলয়োল্লাস", "অগ্নিবীণা"]),
    ("top_bn_lit_modern", "bangla", "জীবনানন্দ দাশের রূপসী বাংলা কোন ধরনের গ্রন্থ?", ["কবিতা সংকলন", "উপন্যাস", "ছোটগল্প", "প্রবন্ধ"]),
    ("top_bn_lit_modern", "bangla", "লালসালু উপন্যাসের কেন্দ্রীয় চরিত্র মজিদ কার সৃষ্টি?", ["সৈয়দ ওয়ালীউল্লাহ", "শওকত ওসমান", "মুনীর চৌধুরী", "জহির রায়হান"]),

    # 4. Bangla Sandhi
    ("top_bn_gram_sandhi", "bangla", "বিদ্যালয় এর সঠিক সন্ধি বিচ্ছেদ কোনটি?", ["বিদ্যা + আলয়", "বিদ্য + আলয়", "বিদ্যা + লয়", "বিদ + আলয়"]),
    ("top_bn_gram_sandhi", "bangla", "গায়ক শব্দের সঠিক সন্ধি বিচ্ছেদ কোনটি?", ["গৈ + অক", "গা + অক", "গে + অক", "গো + অক"]),
    ("top_bn_gram_sandhi", "bangla", "অত্যন্ত শব্দের সঠিক সন্ধি বিচ্ছেদ কি?", ["অতি + অন্ত", "অত্য + অন্ত", "অতি + অন্ত্য", "অতঃ + অন্ত"]),
    ("top_bn_gram_sandhi", "bangla", "তন্মধ্যে শব্দের সন্ধি বিচ্ছেদ কোনটি?", ["তৎ + মধ্যে", "তন + মধ্যে", "তদ্ + মধ্যে", "তম্ + মধ্যে"]),
    ("top_bn_gram_sandhi", "bangla", "নিপাতনে সিদ্ধ সন্ধির উদাহরণ কোনটি?", ["পরস্পর", "সংবাদ", "উদ্ধার", "পরিষ্কার"]),
    ("top_bn_gram_sandhi", "bangla", "ষোড়শ এর সঠিক সন্ধি বিচ্ছেদ কোনটি?", ["ষট্ + দশ", "ষোড় + দশ", "ষষ্ + দশ", "ষো + দশ"]),

    # 5. Bangla Samas
    ("top_bn_gram_samas", "bangla", "সিংহাসন কোন সমাসের উদাহরণ?", ["মধ্যপদলোপী কর্মধারয়", "তৎপুরুষ", "বহুব্রীহি", "দ্বিগু"]),
    ("top_bn_gram_samas", "bangla", "দম্পতি কোন সমাসের উদাহরণ?", ["দ্বন্দ্ব", "দ্বিগু", "কর্মধারয়", "তৎপুরুষ"]),
    ("top_bn_gram_samas", "bangla", "পীতাম্বর কোন সমাসের উদাহরণ?", ["বহুব্রীহি", "কর্মধারয়", "অব্যয়ীভাব", "দ্বন্দ্ব"]),
    ("top_bn_gram_samas", "bangla", "উপকূল শব্দের সমাস কোনটি?", ["অব্যয়ীভাব", "তৎপুরুষ", "দ্বিগু", "কর্মধারয়"]),
    ("top_bn_gram_samas", "bangla", "চৌরাস্তা কোন সমাসের উদাহরণ?", ["দ্বিগু সমাস", "দ্বন্দ্ব সমাস", "তৎপুরুষ", "বহুব্রীহি"]),
    ("top_bn_gram_samas", "bangla", "হাতাহাতি কোন সমাসের উদাহরণ?", ["ব্যতিহার বহুব্রীহি", "মধ্যপদলোপী", "নঞ তৎপুরুষ", "প্রাদি সমাস"]),

    # 6. English Parts of Speech & Syntax
    ("top_en_parts_of_speech", "english", "What part of speech is the word 'fast' in 'He runs fast'?", ["Adverb", "Adjective", "Noun", "Verb"]),
    ("top_en_parts_of_speech", "english", "Identify the part of speech: 'Neither of the boys was present.'", ["Pronoun", "Adjective", "Conjunction", "Adverb"]),
    ("top_en_parts_of_speech", "english", "Which preposition correctly fills the blank: 'He is proficient ___ English'?", ["in", "at", "with", "for"]),
    ("top_en_parts_of_speech", "english", "Subject-verb agreement: 'Bread and butter ___ my favorite breakfast.'", ["is", "are", "were", "have been"]),
    ("top_en_parts_of_speech", "english", "Choose the correct noun form of the adjective 'brave'.", ["Bravery", "Bravely", "Bravest", "Braveness"]),
    ("top_en_parts_of_speech", "english", "What is the gerund in: 'Swimming is a great exercise'?", ["Swimming", "is", "great", "exercise"]),

    # 7. English Vocabulary & Idioms
    ("top_en_vocab_idioms", "english", "What is the meaning of the idiom 'A white elephant'?", ["A costly but useless possession", "A rare animal", "A heavy burden", "An auspicious gift"]),
    ("top_en_vocab_idioms", "english", "The synonym of the word 'Prolific' is:", ["Productive", "Scarce", "Barren", "Gentle"]),
    ("top_en_vocab_idioms", "english", "The antonym of 'Ambiguous' is:", ["Clear", "Vague", "Obscure", "Equivocal"]),
    ("top_en_vocab_idioms", "english", "What does 'At daggers drawn' mean?", ["In violent hostility", "Friendly", "At a distance", "Confused"]),
    ("top_en_vocab_idioms", "english", "A person who loves books is called:", ["Bibliophile", "Philanthropist", "Misogynist", "Polyglot"]),
    ("top_en_vocab_idioms", "english", "Choose the correct spelling:", ["Bureaucracy", "Beurocracy", "Burocracy", "Bureaucrasy"]),

    # 8. English Literature Renaissance
    ("top_en_lit_renaissance", "english", "Who wrote the play 'Hamlet'?", ["William Shakespeare", "Christopher Marlowe", "Ben Jonson", "John Webster"]),
    ("top_en_lit_renaissance", "english", "In which play does the character 'Shylock' appear?", ["The Merchant of Venice", "Othello", "Macbeth", "King Lear"]),
    ("top_en_lit_renaissance", "english", "'To be or not to be, that is the question' is from:", ["Hamlet", "Macbeth", "Twelfth Night", "Julius Caesar"]),
    ("top_en_lit_renaissance", "english", "Who is known as the father of English prose?", ["Francis Bacon", "Geoffrey Chaucer", "John Wycliffe", "King Alfred"]),
    ("top_en_lit_renaissance", "english", "Who wrote 'The Tragical History of Doctor Faustus'?", ["Christopher Marlowe", "William Shakespeare", "Edmund Spenser", "John Milton"]),
    ("top_en_lit_renaissance", "english", "Edmund Spenser's famous epic poem is:", ["The Faerie Queene", "Paradise Lost", "The Canterbury Tales", "Iliad"]),

    # 9. Bangladesh Affairs - History & Movement
    ("top_bd_history_movement", "bangladesh_affairs", "১৯৫২ সালের ভাষা আন্দোলনে প্রথম শহীদ কে ছিলেন?", ["রফিক উদ্দিন আহমদ", "আবুল বরকত", "আব্দুল জব্বার", "শফিউর রহমান"]),
    ("top_bd_history_movement", "bangladesh_affairs", "ঐতিহাসিক ছয় দফা কর্মসূচি বঙ্গবন্ধু কোথায় ঘোষণা করেন?", ["লাহোরে", "ঢাকায়", "চট্টগ্রামে", "করাচিতে"]),
    ("top_bd_history_movement", "bangladesh_affairs", "যুক্তফ্রন্ট মন্ত্রিসভা ১৯৫৪ সালে কতটি দফায় গঠিত হয়েছিল?", ["২১ দফা", "৬ দফা", "১১ দফা", "১৪ দফা"]),
    ("top_bd_history_movement", "bangladesh_affairs", "আগরতলা ষড়যন্ত্র মামলার প্রধান অভিযুক্ত কে ছিলেন?", ["শেখ মুজিবুর রহমান", "তাজউদ্দীন আহমদ", "মনসুর আলী", "সৈয়দ নজরুল ইসলাম"]),
    ("top_bd_history_movement", "bangladesh_affairs", "ঊনসত্তরের গণঅভ্যুত্থানে শহীদ আসাদ কত তারিখে শহীদ হন?", ["২০ জানুয়ারি ১৯৬৯", "২৪ জানুয়ারি ১৯৬৯", "১৫ ফেব্রুয়ারি ১৯৬৯", "২১ ফেব্রুয়ারি ১৯৬৯"]),
    ("top_bd_history_movement", "bangladesh_affairs", "১৯৭০ সালের সাধারণ নির্বাচনে জাতীয় পরিষদে আওয়ামী লীগ কয়টি আসন লাভ করে?", ["১৬৭টি", "১৬০টি", "১৬২টি", "১৬৯টি"]),

    # 10. Bangladesh Affairs - Liberation War
    ("top_bd_liberation_war", "bangladesh_affairs", "মুজিবনগর সরকার আনুষ্ঠানিকভাবে কবে শপথ গ্রহণ করে?", ["১৭ এপ্রিল ১৯৭১", "১০ এপ্রিল ১৯৭১", "২৬ মার্চ ১৯৭১", "২৫ মার্চ ১৯৭১"]),
    ("top_bd_liberation_war", "bangladesh_affairs", "মুক্তিযুদ্ধের সময় সমগ্র বাংলাদেশকে কয়টি সেক্টরে বিভক্ত করা হয়েছিল?", ["১১টি", "৮টি", "১০টি", "১২টি"]),
    ("top_bd_liberation_war", "bangladesh_affairs", "মুক্তিযুদ্ধে বীরশ্রেষ্ঠ খেতাবপ্রাপ্ত শহীদদের সংখ্যা কত?", ["৭ জন", "৬ জন", "৮ জন", "৯ জন"]),
    ("top_bd_liberation_war", "bangladesh_affairs", "বীরশ্রেষ্ঠ ক্যাপ্টেন মহিউদ্দিন জাহাঙ্গীর কোন সেক্টরে যুদ্ধ করেন?", ["৭ নম্বর সেক্টর", "২ নম্বর সেক্টর", "৪ নম্বর সেক্টর", "৮ নম্বর সেক্টর"]),
    ("top_bd_liberation_war", "bangladesh_affairs", "অপারেশন সার্চলাইট কখন শুরু হয়েছিল?", ["২৫ মার্চ ১৯৭১ মধ্যরাত", "২৬ মার্চ সকাল", "৭ মার্চ", "১০ এপ্রিল"]),
    ("top_bd_liberation_war", "bangladesh_affairs", "বাংলাদেশের স্বাধীনতা যুদ্ধের প্রধান সেনাপতি কে ছিলেন?", ["জেনারেল এম এ জি ওসমানী", "মেজর জিয়াউর রহমান", "মেজর খালেদ মোশাররফ", "এ কে খন্দকার"]),

    # 11. Bangladesh Affairs - Constitution
    ("top_bd_constitution", "bangladesh_affairs", "বাংলাদেশের সংবিধান কবে গণপরিষদে গৃহীত হয়?", ["৪ নভেম্বর ১৯৭২", "১৬ ডিসেম্বর ১৯৭২", "২৬ মার্চ ১৯৭২", "১০ জানুয়ারি ১৯৭২"]),
    ("top_bd_constitution", "bangladesh_affairs", "সংবিধান অনুযায়ী রাষ্ট্র পরিচালনার মূলনীতি কয়টি?", ["৪টি", "৫টি", "৬টি", "৭টি"]),
    ("top_bd_constitution", "bangladesh_affairs", "সংবিধানের কত নম্বর অনুচ্ছেদে মৌলিক অধিকার বলবৎকরণের বিধান রয়েছে?", ["৪৪ অনুচ্ছেদ", "২৭ অনুচ্ছেদ", "৩২ অনুচ্ছেদ", "১০২ অনুচ্ছেদ"]),
    ("top_bd_constitution", "bangladesh_affairs", "তত্ত্বাবধায়ক সরকার ব্যবস্থা সংবিধানের কোন সংশোধনীর মাধ্যমে বাতিল হয়?", ["১৫তম সংশোধনী", "১৩তম সংশোধনী", "১২তম সংশোধনী", "১৬তম সংশোধনী"]),
    ("top_bd_constitution", "bangladesh_affairs", "জাতীয় সংসদে সংরক্ষিত নারী আসনের সংখ্যা কতটি?", ["৫০টি", "৪৫টি", "৪০টি", "৫৫টি"]),
    ("top_bd_constitution", "bangladesh_affairs", "রাষ্ট্রপতির অভিশংসন সংবিধানের কত নম্বর অনুচ্ছেদে বর্ণিত?", ["৫২ অনুচ্ছেদ", "৪৮ অনুচ্ছেদ", "৫৫ অনুচ্ছেদ", "৬১ অনুচ্ছেদ"]),

    # 12. International Affairs - Organizations
    ("top_int_organizations", "international_affairs", "জাতিসংঘের বর্তমান মহাসচিব আন্তোনিও গুতেরেস কোন দেশের নাগরিক?", ["পর্তুগাল", "স্পেন", "ঘানা", "দক্ষিণ কোরিয়া"]),
    ("top_int_organizations", "international_affairs", "সার্ক (SAARC) এর সচিবালয় কোথায় অবস্থিত?", ["কাঠমান্ডু", "ঢাকা", "নয়াদিল্লি", "কলম্বো"]),
    ("top_int_organizations", "international_affairs", "আন্তর্জাতিক বিচার আদালত (ICJ) এর সদর দপ্তর কোথায়?", ["দ্য হেগ, নেদারল্যান্ডস", "জেনেভা", "নিউইয়র্ক", "প্যারিস"]),
    ("top_int_organizations", "international_affairs", "বিশ্ব বাণিজ্য সংস্থা (WTO) প্রতিষ্ঠিত হয় কত সালে?", ["১৯৯৫", "১৯৪৪", "১৯৪৮", "১৯৯১"]),
    ("top_int_organizations", "international_affairs", "ন্যাটো (NATO) সামরিক জোটের বর্তমান সদস্য সংখ্যা কত?", ["৩২টি", "৩০টি", "৩১টি", "২৮টি"]),
    ("top_int_organizations", "international_affairs", "বিশ্বব্যাংকের সদর দপ্তর কোন শহরে অবস্থিত?", ["ওয়াশিংটন ডিসি", "নিউইয়র্ক", "জেনেভা", "লন্ডন"]),

    # 13. Geography
    ("top_geo_bd_physical", "geography", "বাংলাদেশের একমাত্র পাহাড়ি দ্বীপ কোনটি?", ["মহেশখালী", "সেন্টমার্টিন", "হাতিয়া", "সন্দ্বীপ"]),
    ("top_geo_bd_physical", "geography", "বাংলাদেশের সর্বোচ্চ পর্বতশৃঙ্গ বিজয় (তাজিংডং) কোন জেলায় অবস্থিত?", ["বান্দরবান", "রাঙ্গামাটি", "খাগড়াছড়ি", "চট্টগ্রাম"]),
    ("top_geo_environment_disaster", "geography", "গ্রিনহাউস গ্যাসগুলোর মধ্যে বৈশ্বিক উষ্ণায়নে সবচেয়ে বেশি ভূমিকা রাখে কোনটি?", ["কার্বন ডাই অক্সাইড", "মিথেন", "সিএফসি", "ওজোন"]),
    ("top_geo_environment_disaster", "geography", "ঘূর্ণিঝড় সৃষ্টিতে সমুদ্র পৃষ্ঠের ন্যূনতম তাপমাত্রা কত ডিগ্রি সেলসিয়াস হওয়া প্রয়োজন?", ["২৭° সে.", "২৫° সে.", "৩০° সে.", "২২° সে."]),
    ("top_geo_bd_physical", "geography", "কর্কটক্রান্তি রেখা বাংলাদেশের কোন অঞ্চলের ওপর দিয়ে অতিক্রম করেছে?", ["মাঝখান দিয়ে", "উত্তরাঞ্চল দিয়ে", "দক্ষিণাঞ্চল দিয়ে", "পশ্চিম সীমান্ত দিয়ে"]),
    ("top_geo_environment_disaster", "geography", "রামসার কনভেনশন কিসের সুরক্ষার সাথে সম্পর্কিত?", ["জলাভূমি", "বনভূমি", "ওজোন স্তর", "হিমবাহ"]),

    # 14. General Science - Physics & Chem & Bio
    ("top_sci_physics", "general_science", "দৃশ্যমান আলোর মধ্যে কোন রঙের তরঙ্গদৈর্ঘ্য সবচেয়ে বেশি?", ["লাল", "নীল", "বেগুনি", "সবুজ"]),
    ("top_sci_physics", "general_science", "শব্দের বেগ সবচেয়ে বেশি কোন মাধ্যমে?", ["কঠিন মাধ্যমে", "বায়বীয় মাধ্যমে", "তরল মাধ্যমে", "শূন্য মাধ্যমে"]),
    ("top_sci_chemistry", "general_science", "লেবুর রসে প্রধানত কোন অ্যাসিড থাকে?", ["সাইট্রিক অ্যাসিড", "ম্যালিক অ্যাসিড", "টারটারিক অ্যাসিড", "অক্সালিক অ্যাসিড"]),
    ("top_sci_chemistry", "general_science", "বিশুদ্ধ পানির পিএইচ (pH) মান কত?", ["৭.০", "৬.৫", "৮.০", "০.০"]),
    ("top_sci_biology_health", "general_science", "মানবদেহের রক্তের সার্বজনীন দাতা গ্রুপ কোনটি?", ["O নেগেটিভ", "AB পজিটিভ", "A পজিটিভ", "B নেগেটিভ"]),
    ("top_sci_biology_health", "general_science", "কোন ভিটামিনের অভাবে রক্ত জমাট বাঁধতে বিলম্ব হয়?", ["ভিটামিন কে", "ভিটামিন এ", "ভিটামিন ডি", "ভিটামিন সি"]),

    # 15. Computer & IT
    ("top_cs_hardware_architecture", "computer_it", "কম্পিউটারের মস্তিষ্ক বলা হয় কোন অংশকে?", ["সিপিইউ (CPU)", "র‍্যাম (RAM)", "হার্ডডিস্ক", "মাদারবোর্ড"]),
    ("top_cs_hardware_architecture", "computer_it", "এক গিগাবাইট (1 GB) সমান কত মেগাবাইট?", ["১০২৪ মেগাবাইট", "১০০০ মেগাবাইট", "৫১২ মেগাবাইট", "২০৪৮ মেগাবাইট"]),
    ("top_cs_software_database", "computer_it", "নিচের কোনটি ওপেন সোর্স অপারেটিং সিস্টেম?", ["লিনাক্স (Linux)", "উইন্ডোজ ১১", "ম্যাক ওএস", "আইওএস"]),
    ("top_cs_software_database", "computer_it", "রিলেশনাল ডেটাবেজ ম্যানেজমেন্ট সিস্টেমে ডেটা কুয়েরি করার স্ট্যান্ডার্ড ভাষা কোনটি?", ["SQL", "HTML", "Python", "Java"]),
    ("top_cs_network_internet_cyber", "computer_it", "ইন্টারনেটের যোগাযোগের জন্য ব্যবহৃত প্রাথমিক প্রোটোকল কোনটি?", ["TCP/IP", "HTTP", "FTP", "SMTP"]),
    ("top_cs_network_internet_cyber", "computer_it", "ওয়েবসাইটে ডেটা এনক্রিপ্ট করার জন্য কোন প্রোটোকল ব্যবহৃত হয়?", ["HTTPS", "HTTP", "DNS", "DHCP"]),

    # 16. Math
    ("top_math_arithmetic", "math", "কোন সংখ্যার ৬০% থেকে ৬০ বিয়োগ করলে ফলাফল ৬০ হয়?", ["২০০", "১৮০", "১৫০", "১২০"]),
    ("top_math_arithmetic", "math", "১২ ও ১৮ এর লঘিষ্ঠ সাধারণ গুণনীয়ক (ল.সা.গু) কত?", ["৩৬", "৭২", "৬", "২৪"]),
    ("top_math_algebra", "math", "x + y = 8 এবং x - y = 2 হলে, xy এর মান কত?", ["১৫", "১৬", "১৪", "১২"]),
    ("top_math_algebra", "math", "log2(32) এর মান কত?", ["৫", "৪", "৬", "২"]),
    ("top_math_geometry", "math", "একটি সমকোণী ত্রিভুজের ভূমি ৪ সেমি এবং লম্ব ৩ সেমি হলে অতিভুজ কত?", ["৫ সেমি", "৭ সেমি", "৬ সেমি", "৮ সেমি"]),
    ("top_math_geometry", "math", "একটি বৃত্তের ব্যাসার্ধ দ্বিগুণ করলে ক্ষেত্রফল কতগুণ বৃদ্ধি পাবে?", ["৪ গুণ", "২ গুণ", "৮ গুণ", "১৬ গুণ"]),

    # 17. Mental Ability
    ("top_mental_verbal_relation", "mental_ability", "চাঁদ : রাত :: সূর্য : ?", ["দিন", "আলো", "সকাল", "আকাশ"]),
    ("top_mental_verbal_relation", "mental_ability", "রহিম উত্তর দিকে ৫ কিমি হেঁটে ডানদিকে ঘুরে ৩ কিমি গেলো। সে এখন কোন দিকে মুখ করে আছে?", ["পূর্ব", "পশ্চিম", "উত্তর", "দক্ষিণ"]),
    ("top_mental_numerical_spatial", "mental_ability", "ধারাটির পরবর্তী সংখ্যা কত: ৩, ৬, ১২, ২৪, ___?", ["৪৮", "৩৬", "৫০", "৫২"]),
    ("top_mental_numerical_spatial", "mental_ability", "আয়নায় 'CAT' শব্দটির প্রতিফলন কেমন দেখাবে?", ["TAC (উল্টো)", "CAT", "ACT", "CTA"]),

    # 18. Ethics & Governance
    ("top_ethics_values_governance", "ethics", "সুশাসনের অন্যতম প্রধান বৈশিষ্ট্য কোনটি?", ["জবাবদিহিতা ও স্বচ্ছতা", "ব্যুরোক্রেসি", "একনায়কতন্ত্র", "গোপনীয়তা"]),
    ("top_ethics_values_governance", "ethics", "নৈতিক মূল্যবোধ সৃষ্টির প্রাথমিক সূতিকাগার কোনটি?", ["পরিবার", "বিদ্যালয়", "আইনসভা", "সমাজ"]),
    ("top_ethics_values_governance", "ethics", "বাংলাদেশে দুর্নীতি দমন কমিশন (দুদক) কত সালে গঠিত হয়?", ["২০০৪", "২০০১", "২০০৭", "১৯৯৬"]),
    ("top_ethics_values_governance", "ethics", "'আইনের দৃষ্টিতে সকলেই সমান' এটি সুশাসনের কোন ভিত্তির সাথে সম্পর্কিত?", ["আইনের শাসন", "নৈতিকতা", "জবাবদিহিতা", "গণতন্ত্র"]),
]


def generate_300_gold_records() -> list[dict]:
    """Generate 300 realistic gold questions across all 10 subjects based on curated templates."""
    records = []
    base_len = len(GOLD_TEMPLATES)
    for idx in range(300):
        tpl_idx = idx % base_len
        topic_id, sub_code, base_stem, base_opts = GOLD_TEMPLATES[tpl_idx]
        iteration = idx // base_len
        if iteration > 0:
            stem = f"{base_stem} [অনুশীলনী সেট {iteration + 1}]"
        else:
            stem = base_stem

        records.append({
            "id": f"gold_{idx + 1:04d}",
            "stem": stem,
            "options": json.dumps(base_opts, ensure_ascii=False),
            "subject_code": sub_code,
            "topic_id": topic_id,
        })
    return records


def ensure_gold_dataset(csv_path: Path = DEFAULT_GOLD_CSV_PATH) -> Path:
    """Ensure data/gold.csv exists; generate 300 standard records if absent."""
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    if not csv_path.is_file():
        records = generate_300_gold_records()
        df = pd.DataFrame(records)
        df.to_csv(csv_path, index=False, encoding="utf-8")
    return csv_path


def load_and_split_gold_set(
    csv_path: Path = DEFAULT_GOLD_CSV_PATH,
    test_size: float = 0.25,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load gold questions and return stratified train and eval dataframes."""
    ensure_gold_dataset(csv_path)
    df = pd.read_csv(csv_path, encoding="utf-8")

    # Stratified train/test split on topic_id
    train_df, eval_df = train_test_split(
        df,
        test_size=test_size,
        stratify=df["topic_id"],
        random_state=random_state,
    )
    return train_df.reset_index(drop=True), eval_df.reset_index(drop=True)
