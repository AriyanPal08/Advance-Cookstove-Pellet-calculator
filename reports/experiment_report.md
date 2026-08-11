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

> **Note:** All predicted durations reported in this table include the fixed safety time buffer (Section 2.5) added prior to pellet-mass calculation. Earlier reporting of certain experiments used the pre-buffer core estimate; all values have been corrected here for consistency across all seven experiments.

<table>
  <thead>
    <tr>
      <th align="center">Exp</th>
      <th align="left">Dish / Procedure</th>
      <th align="left">Utensil Params</th>
      <th align="center">Ambient</th>
      <th align="center">Time: Actual vs Model (Deviation)</th>
      <th align="center">Pellets: Actual vs Model (Deviation)</th>
      <th align="left">Empirical Observations / Remarks</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td align="center"><strong>1</strong></td>
      <td>Water Boil (Lid ON, 5L)</td>
      <td>AL Pot 8L (0.829 kg)</td>
      <td align="center">26°C</td>
      <td align="center"><strong>16 min</strong> vs 20 min (−21.2%)</td>
      <td align="center"><strong>234 g</strong> vs 264 g (−11.4%)</td>
      <td>The final model overpredicted the time required to reach the experimental 99°C endpoint under the covered-pot condition. The observed difference indicates that the present treatment of covered-vessel heat transfer and evaporation warrants further investigation, but the experiment does not independently identify the contribution of the lid to each loss mechanism.</td>
    </tr>
    <tr>
      <td align="center"><strong>2</strong></td>
      <td>Water Boil (Lid OFF, 5L)</td>
      <td>AL Pot 8L (0.829 kg)</td>
      <td align="center">24°C</td>
      <td align="center"><strong>18 min</strong> vs 23.8 min (−24.4%)</td>
      <td align="center"><strong>286 g</strong> vs 309 g (−7.4%)</td>
      <td>The model predicted 23 minutes of cooking time which represented a built-in safety factor to account for convection losses from an open vessel. Additional temperature observations: approx. 94°C at 15 min (pellets consumed ~250 g) and 96°C at 17 min (pellets consumed ~265 g).</td>
    </tr>
    <tr>
      <td align="center"><strong>3</strong></td>
      <td>Tea (5 servings, 1L)</td>
      <td>Kadhai 2.5L (1.092 kg)</td>
      <td align="center">25°C</td>
      <td align="center"><strong>13 min</strong> vs 12 min (+8.3%)</td>
      <td align="center"><strong>151 g</strong> vs 152 g (−0.7%)</td>
      <td>The model tracked the thermal dynamics of smaller volumes of liquids in an open wok very closely: predicted and observed cooking times were therefore relatively close for this test case, although the result represents a single experimental trial.</td>
    </tr>
    <tr>
      <td align="center"><strong>4</strong></td>
      <td>Boiling Milk (0.5L)</td>
      <td>Kadhai 2.5L (1 kg)</td>
      <td align="center">25°C</td>
      <td align="center"><strong>5 min</strong> vs 5 min (0.0%)</td>
      <td align="center"><strong>81 g</strong> vs 65 g (+24.6%)</td>
      <td>Close agreement between the final-model cooking-time prediction and the observed endpoint. The pellet deviation occurred because the experiment was performed under an earlier software version which overestimated the time at 8 minutes. In the final version, the specific heat capacity of milk was corrected, reducing the predicted time to 5 minutes.</td>
    </tr>
    <tr>
      <td align="center"><strong>5</strong></td>
      <td>Rice in Pressure Cooker (4 servings, 480 g)</td>
      <td>SS Pressure Cooker 2L (1.1 kg)</td>
      <td align="center">25°C</td>
      <td align="center"><strong>16 min</strong> vs 10.1 min (+58.4%)</td>
      <td align="center"><strong>350 g</strong> vs 131 g (+167%)</td>
      <td><strong>Critical Failure Mode:</strong> The model predicted the first whistle at 8.5 min vs approx. 8 min experimentally. However, the total predicted cooking time was substantially shorter than the observed 16 min endpoint, and the rice was burnt at the bottom. The model represented the initial heating and pressure-build phase more successfully than the subsequent post-whistle cooking behavior. Under the fixed 0.78 kg h⁻¹ fuel-feed condition, the stove could not reduce its heat input to match the lower energy demand after pressure was established.</td>
    </tr>
    <tr>
      <td align="center"><strong>6</strong></td>
      <td>Mix Veg Curry (4 servings)</td>
      <td>Wok 2.5L (1 kg)</td>
      <td align="center">25°C</td>
      <td align="center"><strong>35 min</strong> vs 33 min (+4.8% deviation reported)</td>
      <td align="center"><strong>455 g</strong> vs 434 g (+6.0% deviation reported)</td>
      <td>A labor-intensive multi-ingredient dish simmered for an extended period. The relatively small time deviation indicates reasonable agreement for this single mixed-ingredient cooking case.</td>
    </tr>
    <tr>
      <td align="center"><strong>7</strong></td>
      <td>Dal Tadka (4 servings)</td>
      <td>Kadhai 2.5L (1 kg)</td>
      <td align="center">33°C</td>
      <td align="center"><strong>34 min</strong> vs 37 min (−8.1%)</td>
      <td align="center"><strong>481 g</strong> vs 481 g (0.0%)</td>
      <td>The slightly shorter cooking duration was offset by the need to reach a higher initial temperature due to the lower differential between the ambient temperature (the warmest of all seven experiments at 33°C) and the desired temperature of the dish. The pellet load was numerically equal to the final-model base pellet estimate; however, because the physical load was selected during an earlier software-development iteration, this agreement should not be interpreted as independent validation.</td>
    </tr>
  </tbody>
</table>

<br>

---

## 3. Graphical Comparative Analysis

### 3.1. Temporal Alignment (Model vs Empirical)
This chart illustrates the temporal accuracy of the model across all seven experiments. Note the close alignment in long-duration complex dishes (Dal Tadka, Mix Veg) versus the significant deviation in the Rice (Pressure Cooker) experiment due to the post-whistle cooking phase.

<p align="center">
  <img src="./charts/chart_time_comparison.png" alt="Cooking Time: Model Prediction vs Experimental Result" width="800">
</p>

### 3.2. Pellet Consumption Alignment (Model vs Empirical)
This chart compares the model-predicted pellet consumption against the actual pellet usage measured in each experiment. The Rice (Pressure Cooker) experiment shows the most significant deviation at +167%.

<p align="center">
  <img src="./charts/chart_pellet_comparison.png" alt="Pellet Consumption: Model Prediction vs Experimental Result" width="800">
</p>

### 3.3. Cooking Time Deviation Analysis
A horizontal bar chart representing the percentage deviation in cooking time for each experiment. Green bars indicate deviations within ±10%, yellow for 10–25%, and red for deviations exceeding 25%.

<p align="center">
  <img src="./charts/chart_time_deviation.png" alt="Cooking Time Deviation (%) from Model Prediction" width="800">
</p>

### 3.4. Pellet Consumption Deviation Analysis
Similar deviation analysis for pellet consumption, highlighting experiments where the model significantly over- or under-predicted fuel requirements.

<p align="center">
  <img src="./charts/chart_pellet_deviation.png" alt="Pellet Consumption Deviation (%) from Model Prediction" width="800">
</p>

### 3.5. Combined Time & Pellet Deviation Analysis
A combined view showing both temporal and pellet consumption deviations side by side for each experiment, enabling direct comparison of model accuracy across both metrics.

<p align="center">
  <img src="./charts/chart_combined_deviation.png" alt="Combined Time & Pellet Deviation Analysis" width="800">
</p>

### 3.6. Temperature Rise Profile — Experiment 2 (Water Boil, Lid OFF)
The temperature approach to boiling was characterized with intermediate measurements during Experiment 2. The profile shows the heating curve from ambient (24°C) to 99°C, with the model-predicted completion time marked for comparison.

<p align="center">
  <img src="./charts/chart_temp_profile_exp2.png" alt="Experiment 2: Temperature Rise Profile" width="800">
</p>

### 3.7. Pellet Consumption Over Time — Experiment 2 (Water Boil, Lid OFF)
The progressive pellet consumption was tracked during Experiment 2, providing insight into the fuel usage rate during the water heating process.

<p align="center">
  <img src="./charts/chart_pellet_consumption_profile_exp2.png" alt="Experiment 2: Pellet Consumption Over Time" width="800">
</p>

### 3.8. Model Accuracy: Time vs Pellet Deviation
A scatter plot mapping each experiment's time deviation against its pellet deviation. The shaded region represents the ±10% accuracy zone. Experiments falling within this zone demonstrate strong model-experiment agreement.

<p align="center">
  <img src="./charts/chart_accuracy_summary.png" alt="Model Accuracy: Time vs Pellet Deviation" width="800">
</p>

### 3.9. Model Accuracy Radar — Absolute Time Deviation
A radar chart visualizing the absolute time deviation for each experiment, providing a holistic view of which cooking scenarios the model handles well and where it struggles.

<p align="center">
  <img src="./charts/chart_absolute_error_radar.png" alt="Model Accuracy Radar: Absolute Time Deviation" width="800">
</p>

### 3.10. Effect of Ambient Temperature on Model Accuracy
A scatter plot examining whether ambient temperature correlates with model prediction accuracy, given that Experiment 7 was conducted under the warmest conditions (33°C).

<p align="center">
  <img src="./charts/chart_ambient_temp_effect.png" alt="Effect of Ambient Temperature on Model Accuracy" width="800">
</p>

### 3.11. Model Performance Heatmap
A heatmap representation of deviation magnitudes across all experiments for both time and pellet metrics. Green indicates close agreement, while red highlights areas requiring model improvement.

<p align="center">
  <img src="./charts/chart_model_performance_heatmap.png" alt="Model Performance Heatmap" width="800">
</p>

---

## 4. Empirical Derivation of the Mass Burn Rate Constant

To validate the `0.78 kg/hr` constant heavily utilized in the simulator's mathematics, three independent combustion baseline experiments were conducted. In each test, 550 g of mustard husk pellets were loaded into the Tadka Chulha and burned for roughly 40 minutes to completion.

<p align="center">
  <img src="./charts/chart_burn_rate_validation.png" alt="Burn Rate Validation Tests" width="700">
</p>

**Mathematical Conclusion:**
*   **Average Pellets Combusted:** 550 g − (~30 g residual ash) = 520 g
*   **Average Burn Duration:** 40 minutes
*   **Calculated Burn Rate:** 520 g / 40 min = 13 g/min
*   **Hourly Conversion:** 13 g/min × 60 min/hr = **0.78 kg/hr**

The experimental data confirms the fundamental 0.78 kg/hr constant used in the `FAN_HIGH` configuration of the simulation engine.

---

## 5. Detailed Experiment Narratives

### Experiment 1: Water Boiling with Lid On (5 liters)
Five liters of plain water were brought to boil in an 8-litre aluminum pot weighing 0.829 kg with a lid on. The ambient temperature was recorded as 26°C. The model predicted it would take 20 minutes to boil the water. In reality, it took 16 minutes to reach 99°C, which was 21.2% faster than predicted, with a consumption of 234 g of pellets. The final model's base time-derived pellet quantity was 264 g, which resulted in a −11.4% deviation. The experiment therefore showed that the final model overpredicted the time required to reach the experimental 99°C endpoint under the covered-pot condition. The observed difference indicates that the present treatment of covered-vessel heat transfer and evaporation warrants further investigation, but the experiment does not independently identify the contribution of the lid to each loss mechanism. Note that this predicted duration includes the fixed safety time buffer (Section 2.5) added prior to pellet-mass calculation; earlier reporting of this experiment used the pre-buffer core estimate, which has been corrected here for consistency with the other six experiments.

### Experiment 2: Water Boiling with Lid Off (5 liters)
This was similar to the preceding experiment, except that the aluminum pot was operated without a lid. The ambient temperature was 24°C. The model predicted it would take 23.8 minutes to boil the water. In the actual experiment, it took 18 minutes to reach 99°C, which was 24.4% faster than predicted. The total consumption of pellets was 286 g against 309 g suggested by the final model's base time-derived pellet quantity, with a −7.4% deviation. The model predicted 23 minutes of cooking time, which represented a built-in safety factor to account for convection losses from an open vessel. Additional temperature observations were recorded during the heating process to characterize the approach to boiling; approximately 94°C was observed at 15 min (pellets consumed ~250 g) and 96°C at 17 min (pellets consumed ~265 g). Note that this predicted duration includes the fixed safety time buffer (Section 2.5) added prior to pellet-mass calculation; earlier reporting of this experiment used the pre-buffer core estimate, which has been corrected here for consistency with the other six experiments.

### Experiment 3: Tea (5 servings, 1 liter)
Tea for five servings with a total volume of 1 liter (taking an assumption of 200 ml per person) was brewed in a 2.5-liter kadhai weighing 1.092 kg. The ambient temperature was 25°C. The model predicted 12 minutes of cooking time. It took 13 minutes in reality, with an 8.3% deviation. The total consumption of pellets was 151 g against 152 g suggested by the final model's base time-derived quantity, with a −0.7% deviation. It was established that the model tracked the thermal dynamics of smaller volumes of liquids in an open wok very closely: the predicted and observed cooking times were therefore relatively close for this test case, although the result represents a single experimental trial.

### Experiment 4: Boiling Milk (0.5 liters)
Milk in the volume of 0.5 liters was brought to a boil in a 2.5-liter kadhai weighing 1 kg. The ambient temperature was 25°C. The model predicted 5 minutes of cooking time. Real-world testing was also consistent with that prediction, with no deviation. The consumption of pellets was 81 g against 65 g suggested by the final model, with a positive 24.6% deviation. The reason for this deviation was that this experiment had been performed under an earlier version of the software which overestimated the time needed to boil milk at 8 minutes. Thus, the operator loaded the pellets in accordance with that estimate. In the final version of the software, the specific heat capacity of milk was corrected, which reduced the predicted time to 5 minutes. Experiment 4 showed close agreement between the final-model cooking-time prediction and the observed endpoint under the tested conditions.

### Experiment 5: Rice in Pressure Cooker (4 servings, 480 g)
Rice for four servings (480 g) was cooked in a 2-liter stainless steel pressure cooker weighing 1.1 kg. The ambient temperature was 25°C. The model predicted the total cooking time to be 10.1 minutes. The rice was actually cooked for 16 minutes and it came out burnt on the bottom, with a positive 58.4% deviation in time. The consumption of pellets was 350 g against 131 g predicted by the final model's base time-derived quantity, with a positive 167% deviation. The model predicted the first whistle at 8.5 min, compared with approximately 8 min experimentally. However, the total predicted cooking time was substantially shorter than the observed 16-min endpoint, and the rice was burnt at the bottom. The result indicates that the model represented the initial heating and pressure-build phase more successfully than the subsequent post-whistle cooking behavior. Under the fixed 0.78 kg h⁻¹ fuel-feed condition, the stove could not reduce its heat input to match the lower energy demand after pressure was established. The present pressure-cooker formulation therefore does not adequately represent the coupled behavior of pressure, evaporation, water availability, and post-whistle cooking under the fixed-feed stove configuration.

*Figure 1: Experimental preparation of basmati rice in the Tadka Chulha using a 2-L pressure cooker.*

### Experiment 6: Mix Vegetable Curry (4 servings)
Mix vegetable curry for four servings was cooked in a 2.5-liter wok weighing 1 kg. The ambient temperature was 25°C. The model predicted 33 minutes of cooking time. Real-world testing required 35 minutes, which represented a 4.8% deviation. The consumption of pellets was 455 g against 434 g predicted by the final time-derived model, also with a 6.0% deviation. Experiment 6 involved a labor-intensive multi-ingredient dish which had to be simmered for an extended period of time. The relatively small time deviation indicates reasonable agreement for this single mixed-ingredient cooking case.

### Experiment 7: Dal Tadka (4 servings)
Dal tadka for four servings was cooked in a 2.5-liter kadhai (wok) weighing 1 kg. The ambient temperature was as high as 33°C, which was the warmest of all seven experiments. The model predicted 37 minutes of cooking time. Real-world testing took 34 minutes, which represented an 8.1% deviation. The consumption of pellets was 481 g. The pellet load was numerically equal to the final-model base pellet estimate for this case; however, because the physical load was selected during an earlier software-development iteration, this agreement should not be interpreted as independent validation of the final pellet-recommendation algorithm. The slightly shorter duration of cooking was offset by the need to reach a higher initial temperature due to the lower differential between the ambient temperature and the desired temperature of the dish.

---

## 6. Practical Training Remarks & Future Work

For future training manuals and user guides, the data from **Experiment 5 (Rice in Pressure Cooker)** must be heavily emphasized. 

While the mathematical simulation successfully predicted the point of sensible heating (First Boil at ~8 minutes), the forced-draft continuous output of the Tadka Chulha is too intense for standard stovetop water-to-rice ratios. Because the fan continually supplies 0.78 kg/hr of energy without modulation, the pressure cooker evaporates its water jacket rapidly, leading to the observed 16-minute burnt bottom.

**Training Directive for End-Users:**
1.  Increase the physical water-to-rice volume by 20–30% when cooking on a gasifier stove to accommodate the accelerated phase-change evaporation.
2.  Alternatively, the operator must manually cut off the fan immediately after the first whistle (approx. 8.5 minutes) and allow the residual thermal mass of the stove and the pressure cooker to finish the kinetic simmering passively.
