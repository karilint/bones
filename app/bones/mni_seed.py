"""Version-controlled seed values sourced from the MNI Excel workbooks."""

ELEMENT_RULES = [
    ("acetabulum", 1), ("astragalus", 1), ("atlas", 1), ("axis", 1),
    ("bone nonidentifiable", 1000), ("calcaneus", 1), ("carpal indet", 8),
    ("caudal vertebra", 4), ("cervical vertebra", 7), ("coccyx", 1),
    ("cranium", 1000), ("cuneiform", 1), ("distal forelimb phalanx", 5),
    ("distal hindlimb phalanx", 5), ("distal phalanx", 5),
    ("external and middle cuneiform", 1), ("femur", 1), ("fibula", 1),
    ("hemi-innominate", 1), ("hemi-mandible", 1), ("horn core", 1),
    ("humerus", 1), ("illium", 1), ("innominate", 1),
    ("intermediate forelimb phalanx", 5),
    ("intermediate hindlimb phalanx", 5), ("intermediate phalanx", 5),
    ("long bone epiphysis", 40), ("long bone indet", 40),
    ("long bone near epiphysis", 40), ("long bone shaft", 40),
    ("lumbar vertebra", 6), ("lunar", 1), ("magnum", 1),
    ("mandible", 1), ("maxilla", 1), ("metacarpal", 5),
    ("metacarpal ii", 1), ("metacarpal iv", 1), ("metatarsal", 5),
    ("metatarsal ii", 1), ("metatarsal iv", 1), ("naviculo-cuboid", 1),
    ("patella", 1), ("pisiform", 1), ("proximal forelimb phalanx", 5),
    ("proximal hindlimb phalanx", 5), ("proximal phalanx", 5),
    ("radioulna", 1), ("radius", 1), ("rib", 18), ("sacrum", 1),
    ("scaphoid", 1), ("scapula", 1), ("sesamoid", 1), ("sternum", 1),
    ("tarsal indet", 7), ("teeth", 32), ("thoracic vertebra", 18),
    ("tibia", 1), ("ulna", 1), ("unciform", 1), ("vertebra", 31),
]

# Axial/midline elements are unpaired; remaining seeded elements are paired.
UNPAIRED_ELEMENTS = {
    "atlas", "axis", "bone nonidentifiable", "caudal vertebra",
    "cervical vertebra", "coccyx", "cranium", "lumbar vertebra",
    "sacrum", "sternum", "teeth", "thoracic vertebra", "vertebra",
}

TAXON_RULES = [
    ("Mammalia indet", "Mammalia indet"), ("Mammalia indet.", "Mammalia indet"),
    ("ostrich", "ostrich"), ("ungulate", "Ungulata"), ("Ungulata", "Ungulata"),
    ("Unknown taxon", "Unknown taxon"),
    ("Aves (medium)", "Aves (medium)"), ("Aves (small)", "Aves (small)"),
    ("Baboon troop", "Papio anubis"), ("Black rhino", "Diceros bicornis"),
    ("black rhinoceros", "Diceros bicornis"),
    ("Bovidae (large)", "Bovidae (large)"),
    ("Bovidae (medium)", "Bovidae (medium)"),
    ("Bovidae (small)", "Bovidae (small)"),
    ("buffalo", "Syncerus caffer"),
    ("Bushbuck", "Tragelaphus scriptus"),
    ("bushpig", "Potamochoerus larvatus"),
    ("Cheetah", "Acinonyx jubatus"),
    ("cow (domestic)", "Bos taurus indicus"),
    ("Cattle", "Bos taurus indicus"), ("eland", "Taurotragus oryx"),
    ("elephant", "Loxodonta africana"), ("Gerenuk", "Litocranius walleri"),
    ("giraffe", "Giraffa camelopardalis"),
    ("Grant's gazelle", "Nanger granti"), ("Grevy's zebra", "Equus grevyi"),
    ("hare", "Lepus"), ("hartebeest", "Alcelaphus buselaphus"),
    ("Hippo", "Hippopotamus amphibius"), ("Hyaenidae", "Hyaenidae"),
    ("Hybrid zebra", "Equus"), ("Hyena", "Crocuta"),
    ("impala", "Aepyceros melampus"), ("Jackal", "Canis mesomelas"),
    ("lion", "Panthera leo"), ("Oryx", "Oryx beisa"),
    ("Patas monkey", "Erythrocebus patas"),
    ("Plains zebra", "Equus burchellii"), ("reedbuck", "Redunca redunca"),
    ("Rhinocerotidae", "Rhinocerotidae"),
    ("Southern white rhino", "Ceratotherium simum simum"),
    ("spotted hyaena", "Crocuta crocuta"),
    ("Steenbok", "Raphicerus campestris"),
    ("Taurotragus", "Taurotragus oryx"),
    ("Thompson's gazelle", "Eudorcas thomsonii"),
    ("Thomson's gazelle", "Eudorcas thomsonii"),
    ("tree hyrax", "Dendrohyrax arboreus"),
    ("vervet", "Chlorocebus pygerythrus"),
    ("warthog", "Phacochoerus africanus"),
    ("waterbuck", "Kobus ellipsiprymnus"), ("Wild dog", "Lycaon pictus"),
    ("zebra", "Equus burchellii"),
]

DEFAULT_EXCLUDED_TAXA = {
    "aves (medium)", "aves (small)", "mammalia indet", "mammalia indet.",
    "ostrich", "ungulate", "ungulata", "unknown taxon",
}

WEATHERING_RULES = [
    ("0", "0", 0, 1),
    ("0-1", "0-1", 0.5, 2.5),
    ("1", "1", 0.5, 2.5),
    ("1-2", "1-2", 2, 5),
    ("2", "2", 2, 5),
    ("2-3", "2-3", 4, 8),
    ("3", "3", 4, 8),
    ("3-4", "3-4", 7, 20),
    ("4", "4", 7, 20),
    ("4-5", "4-5", 10, 25),
    ("5", "5", 10, 25),
    ("6", "6", 10, 25),
]

WEATHERING_CORRECTED_RANGES = {
    "0": (0, 5), "0-1": (0, 5), "1": (0, 5),
    "1-2": (0, 5), "2": (0, 5),
    "2-3": (4, 25), "3": (4, 25), "3-4": (4, 25),
    "4": (4, 25), "4-5": (4, 25), "5": (4, 25), "6": (4, 25),
}
