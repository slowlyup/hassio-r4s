SUPPORTED_DEVICES = {
    'RK-M170S': 0,
    'RK-M171S': 0,
    'RK-M173S': 0,
    'RK-G200S': 2,
    'RK-G200S-E': 2,
    'RK-G201S': 1,
    'RK-G202S': 1,
    'RK-G203S': 1,
    'RK-G210S': 1,
    'RK-G211S': 1,
    'RK-G212S': 1,
    'RK-G214S': 1,
    'RK-G240S': 1,
    'RK-M216S': 2,
    'RK-M216S-E': 2,
    'RAC-3706S': 3,
    'RFS-HPL001': 4,
    'RSP-103S': 4,
    'RCH-7001S': 4,
    'RMC-M800S': 5,
    'RMC-M223S': 5,
    'RMC-M92S': 5,
    'RMC-M92S-E': 5,
    'RMC-M40S': 5,

    # default bluetooth adapters name
    'RFS-KKL002': 1,  # aka RK-G210S RK-G211S, RK-G212S
    'RFS-KKL003': 1,  # aka RK-G214S
    'RFS-KKL004': 1   # aka RK-G213S, RK-G214S
}

COOKER_PROGRAMS = {
    'rice': ['01', '00', '64', '00', '23', '00', '00', '01'],
    'slow_cooking': ['02', '00', '61', '03', '00', '00', '00', '01'],
    'pilaf': ['03', '00', '6e', '01', '00', '00', '00', '01'],
    'frying_vegetables': ['04', '01', 'b4', '00', '12', '00', '00', '01'],
    'frying_fish': ['04', '02', 'b4', '00', '0c', '00', '00', '01'],
    'frying_meat': ['04', '03', 'b4', '00', '0f', '00', '00', '01'],
    'stewing_vegetables': ['05', '01', '64', '00', '28', '00', '00', '01'],
    'stewing_fish': ['05', '02', '64', '00', '23', '00', '00', '01'],
    'stewing_meat': ['05', '03', '64', '01', '00', '00', '00', '01'],
    'pasta': ['06', '00', '64', '00', '08', '00', '00', '01'],
    'milk_porridge': ['07', '00', '5f', '00', '23', '00', '00', '01'],
    'soup': ['08', '00', '63', '01', '00', '00', '00', '01'],
    'yogurt': ['09', '00', '28', '08', '00', '00', '00', '00'],
    'baking': ['0a', '00', '91', '00', '2d', '00', '00', '01'],
    'steam_vegetables': ['0b', '01', '64', '00', '1e', '00', '00', '01'],
    'steam_fish': ['0b', '02', '64', '00', '19', '00', '00', '01'],
    'steam_meat': ['0b', '03', '64', '00', '28', '00', '00', '01'],
    'hot': ['0c', '00', '64', '00', '28', '00', '00', '01']}
