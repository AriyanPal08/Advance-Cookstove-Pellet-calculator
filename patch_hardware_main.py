with open('hardware/main.py', 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('P_in_kw=P_in_kw, A_m2=inp["A_m2"], k_conv=inp["k_conv_current"],', 'P_in_kw=P_in_kw, A_m2=inp["A_m2"], A_top=inp["A_top"], k_conv=inp["k_conv_current"],')
with open('hardware/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Patched main.py')
