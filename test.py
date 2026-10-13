grouped_by_level_str = ""
LEVEL_DESCR = [
    {
        "level_id": 1,
        "level_symbol": "🟢",
        "level_name": "Новичок",
    },
    {
        "level_id": 2,
        "level_symbol": "🟡",
        "level_name": "База",
    },
    {
        "level_id": 3,
        "level_symbol": "🟠",
        "level_name": "Уверенная база",
    },
    {
        "level_id": 4,
        "level_symbol": "🔵",
        "level_name": "Опытный, уровень 1"
    },
    {
        "level_id": 5,
        "level_symbol": "🟣",
        "level_name": "Условно эксперт (выше 4)",
    }
]
levels = [1,1,1,2,3,5,4,3,1,3,2]

reg_dict: dict = {level['level_symbol']: 0 for level in LEVEL_DESCR}
level_dict: dict = {level['level_id']: level['level_symbol'] for level in LEVEL_DESCR}

for level_id in levels:
    reg_dict[level_dict[level_id]] += 1
        
for key in reg_dict:
    grouped_by_level_str += f"\n{key}: 👤{reg_dict[key]}"
    
print(grouped_by_level_str)