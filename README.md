# NEW CHANGES coming soon v10
updating the calculation of 3 phase combustion 
adding features of slecting material of which utensils are made up of
# Advance Cookstove Pellet calculator
A thermodynamic modeling tool to calculate biomass pellet requirements for improved cookstoves. Uses a 5-term energy balance model with 3-phase combustion dynamics, wind/lid effects, and realistic Indian cooking parameters.
# Biomass Cookstove Pellet Calculator

A thermodynamic modeling tool to estimate biomass pellet fuel requirements for improved cookstoves used in rural India. The model uses a detailed 5-term energy balance combined with a 3-phase combustion profile to provide realistic pellet consumption estimates for traditional Indian dishes.

## Features

- **5-Term Energy Balance**: Accounts for food sensible heat, water heating, vessel thermal mass, vessel heat loss, and evaporation.
- **3-Phase Combustion Modeling**: Divides pellet burning into Ignition, Steady, and Decline phases for more accurate time and fuel estimation.
- **Realistic Indian Cooking Parameters**: Supports 10+ common dishes (Rice, Dal Tadka, Chicken Curry, Sambar, Mix Veg, etc.) with validated water ratios and cooking times.
- **Environmental & Operational Factors**: Includes effects of wind, cooking location (indoor/outdoor), lid usage, and vessel mass.
- **Batch Scaling**: Uses physically motivated sub-linear time scaling for multi-person cooking.
- **Pressure Cooker Support**: Special evaporation and time reduction factors for pressure cooking.
- **Interactive CLI**: User-friendly command-line interface with smart suggestions and detailed energy breakdown.

## How It Works

The model calculates the total thermal energy required to cook a dish using:
Q_total = Q_food + Q_water + Q_vessel_mass + Q_vessel_loss + Q_evaporation
