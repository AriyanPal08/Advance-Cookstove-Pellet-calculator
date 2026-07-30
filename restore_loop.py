import re
import shutil

with open('old2_utensil_db.py', 'r', encoding='utf-16') as f:
    content = f.read()

match = re.search(r'UTENSIL_DB: dict\[str, Utensil\] = \{\}\n\nfor name, spec in MANUFACTURER_SPECS\.items\(\):.*?pressure_rating_kpa=spec\.get\("pressure_rating_kpa"\)\n    \)\n', content, flags=re.DOTALL)

if match:
    db_loop = match.group(0).replace(': dict[str, Utensil]', '') # strip type hint for micropython
    with open('utensil_db.py', 'r', encoding='utf-8') as f:
        new_content = f.read()
    
    # Insert right before UTENSIL_CATEGORIES
    new_content = new_content.replace('UTENSIL_CATEGORIES: list[tuple[str, list[str]]] = [', db_loop + '\n\nUTENSIL_CATEGORIES: list[tuple[str, list[str]]] = [')
    
    with open('utensil_db.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    shutil.copyfile('utensil_db.py', 'hardware/utensil_db.py')
    print('Restored UTENSIL_DB loop to both root and hardware!')
else:
    print('Failed to find UTENSIL_DB loop in old2_utensil_db.py')
