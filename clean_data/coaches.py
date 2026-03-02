import sys
import os
import numpy as np
import matplotlib as plt

ROOT = r"C:\Users\aycja\git repos\SacramentoKingsAnalyasis"
sys.path.append(ROOT)

import load_data
coaches_df = load_data.coaches

# print(coaches_df.iloc[0])
coaches_df.drop('Rk', axis=1, inplace=True)
# print(coaches_df)

#find the top three coaches that have made the most playoffs
coaches_df.sort_values(by="Plyfs", inplace=True, ascending=False)
coaches_who_made_playoffs = coaches_df[coaches_df['Plyfs'].notna()]

coaches_above_par_reg_szn = coaches_df[coaches_df['W/L%'] >= 0.500] # coaches with a overall win loss ratio above 0.500

