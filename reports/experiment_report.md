<div align="center">
  <h1>Evaluation of fuel requirements w.r.t. food cooking and operation time using biomass pellet cookstove</h1>
  <h3>Created by:</h3>
  <p><strong>Ariyan Pal, Yash Tyagi, and Himanshu Kumar</strong></p>
  <h3>Under the Guidance of:</h3>
  <p><strong>Prof. S.K. Tyagi</strong></p>
  <h3>Mentor:</h3>
  <p><strong>S.P. Parameshwaran</strong></p>
  <br>
  <hr>
</div>

<br>

# Laboratory Experimental Validation Report

**Project Phase:** Empirical Model Validation & Burn Rate Standardization<br>
**Fuel Analyzed:** Mustard Husk Pellets<br>
**Apparatus:** Tadka Chulha (Forced Draft Biomass Stove)

---

## 1. Methodology & Apparatus Specifications
To validate the transient physics models driving the cookstove simulator, a series of seven standard cooking experiments and three burn rate verification tests were conducted indoors. 

**Standardized Constants:**
*   **Stove Mass:** 5.350 kg (Tadka Chulha with fan modular attached)
*   **Thermal Efficiency Constant:** 47% (0.47)
*   **Fuel Type:** Mustard Husk Pellets
*   **Calculated Mass Burn Rate:** 0.78 kg/hr (13 g/min)

All cooking experiments recorded ambient temperature, exact utensil mass/capacity, total mass of pellets combusted, and exact time taken to achieve the culinary goal compared against the model's simulated outputs.

---

## 2. Experimental Data & Deviation Analysis

The table below breaks down the deviation between the theoretical simulation and the empirical laboratory results for both **Cooking Time** and **Pellet Consumption**.

<table>
  <thead>
    <tr>
      <th align="center">Exp</th>
      <th align="left">Dish / Procedure</th>
      <th align="left">Utensil Params</th>
      <th align="center">Ambient</th>
      <th align="center">Time Diff (Actual vs Model)</th>
      <th align="center">Mass Diff (Actual vs Model)</th>
      <th align="left">Empirical Observations / Remarks</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td align="center"><strong>1</strong></td>
      <td>Water Boil (Lid ON, 5L)</td>
      <td>AL Pot 8L (0.829 kg)</td>
      <td align="center">26°C</td>
      <td align="center"><strong>16m</strong> vs 18m (-11.1%)</td>
      <td align="center"><strong>264g</strong> vs 234g (+12.8%)</td>
      <td>The lid efficiently trapped heat, leading to a faster boil. Total pellet usage slightly higher due to 19m total burn duration despite reaching 99°C at 16m.</td>
    </tr>
    <tr>
      <td align="center"><strong>2</strong></td>
      <td>Water Boil (Lid OFF, 5L)</td>
      <td>AL Pot 8L (0.829 kg)</td>
      <td align="center">24°C</td>
      <td align="center"><strong>18m</strong> vs 22m (-18.1%)</td>
      <td align="center"><strong>303g</strong> vs 286g (+5.9%)</td>
      <td>Repeated runs yielded consistent results (15m/94°C and 17m/96°C). The model's 22m prediction safely overestimates convection heat loss.</td>
    </tr>
    <tr>
      <td align="center"><strong>3</strong></td>
      <td>Tea (5 servings, 1L)</td>
      <td>Kadhai 2.5L (1 kg)</td>
      <td align="center">25°C</td>
      <td align="center"><strong>13m</strong> vs 12m (+8.3%)</td>
      <td align="center"><strong>151g</strong> vs 156g (-3.2%)</td>
      <td>Exceptional alignment. Heat transfer characteristics for small liquid batches in open Kadhais are highly accurate.</td>
    </tr>
    <tr>
      <td align="center"><strong>4</strong></td>
      <td>Boiling Milk (0.5L)</td>
      <td>Kadhai 2.5L (1 kg)</td>
      <td align="center">25°C</td>
      <td align="center"><strong>5m</strong> vs 5m (0.0%)</td>
      <td align="center"><strong>81g</strong> vs 65g (+24.6%)</td>
      <td>Perfect temporal alignment. The new model successfully corrected the previous 8m overestimation by accurately tuning milk's specific heat.</td>
    </tr>
    <tr>
      <td align="center"><strong>5</strong></td>
      <td>Rice (4 servings, 480g)</td>
      <td>Pressure Cooker 2L (1.1 kg)</td>
      <td align="center">25°C</td>
      <td align="center"><strong>16m</strong> vs 10.1m (+58.4%)</td>
      <td align="center"><strong>350g</strong> vs 131g (+167%)</td>
      <td><strong>Critical Failure Mode:</strong> The model perfectly predicted the first boil (8m vs 8.5m), but the overall process took 16m and resulted in a burnt bottom. The kinetic simmer phase inside the pressure vessel dehydrated too rapidly, indicating a practical limit on water-to-rice ratios over forced draft stoves.</td>
    </tr>
    <tr>
      <td align="center"><strong>6</strong></td>
      <td>Mix Veg Curry (4 servings)</td>
      <td>Kadhai 2.5L (1 kg)</td>
      <td align="center">25°C</td>
      <td align="center"><strong>35m</strong> vs 33m (+6.0%)</td>
      <td align="center"><strong>455g</strong> vs 429g (+6.0%)</td>
      <td>Excellent alignment for a highly complex, multi-ingredient dish with long kinetic simmering.</td>
    </tr>
    <tr>
      <td align="center"><strong>7</strong></td>
      <td>Dal Tadka (4 servings)</td>
      <td>Kadhai 2.5L (1 kg)</td>
      <td align="center">33°C</td>
      <td align="center"><strong>34m</strong> vs 37m (-8.1%)</td>
      <td align="center"><strong>481g</strong> vs 481g (0.0%)</td>
      <td>Very good alignment. The slightly higher ambient temperature (33°C) directly accelerated the sensible heating phase.</td>
    </tr>
  </tbody>
</table>

<br>

---

## 3. Graphical Comparative Analysis

### 3.1. Temporal Alignment (Model vs Empirical)
This graph illustrates the temporal accuracy of the model. Note the strict alignment in long-duration complex dishes (Dal Tadka, Mix Veg) versus the significant deviation in the Rice (Pressure Cooker) experiment due to kinetic phase evaporation.

<p align="center">
  <img src="./images/detailed_time_comparison.png" alt="Time Comparison" width="800">
</p>


---

## 4. Empirical Derivation of the Mass Burn Rate Constant

To validate the `0.78 kg/hr` constant heavily utilized in the simulator's mathematics, three independent combustion baseline experiments were conducted. In each test, 550g of mustard husk pellets were loaded into the Tadka Chulha and burned for roughly 40 minutes to completion.

<p align="center">
  <img src="./images/detailed_ash_validation.png" alt="Ash Validation" width="700">
</p>

**Mathematical Conclusion:**
*   **Average Pellets Combusted:** 550g - (~30g residual ash) = 520g
*   **Average Burn Duration:** 40 minutes
*   **Calculated Burn Rate:** 520g / 40min = 13 g/min
*   **Hourly Conversion:** 13 g/min × 60 min/hr = **0.78 kg/hr**

The experimental data unequivocally confirms the fundamental 0.78 kg/hr constant used in the `FAN_HIGH` configuration of the simulation engine.

---

## 5. Practical Training Remarks & Future Work

For future training manuals and user guides, the data from **Experiment 5 (Rice in Pressure Cooker)** must be heavily emphasized. 

While the mathematical simulation flawlessly predicted the point of sensible heating (First Boil at 8 minutes), the forced-draft continuous output of the Tadka Chulha is too intense for standard stovetop water-to-rice ratios. Because the fan continually supplies 0.78 kg/hr of energy without modulation, the pressure cooker evaporates its water jacket rapidly, leading to the observed 16-minute burnt bottom.

**Training Directive for End-Users:**
1.  Increase the physical water-to-rice volume by 20-30% when cooking on a gasifier stove to accommodate the accelerated phase-change evaporation.
2.  Alternatively, the operator must manually cut off the fan immediately after the first whistle (approx. 8.5 minutes) and allow the residual thermal mass of the stove and the pressure cooker to finish the kinetic simmering passively.
