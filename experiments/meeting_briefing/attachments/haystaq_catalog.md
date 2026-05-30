# Haystaq constituent-sentiment catalog (L2-verified)

The **complete, L2-verified** list of polarized constituent-sentiment columns available to the
`meeting_briefing` experiment. Loaded on demand by the agent at Step 6 (do NOT query any catalog or
dictionary table at runtime — every column you can use is listed here). Grouped into 9 policy topics;
each entry pairs a column name with a one-line `meaning` that already encodes direction
(e.g. `hs_gun_control_support` -> "supports gun control").

Delivered as a manifest attachment to `/workspace/haystaq_catalog.md`.

**housing** — Housing affordability, gentrification views, homeownership status

| Column                               | Meaning                                            |
| ------------------------------------ | -------------------------------------------------- |
| `hs_affordable_housing_gov_has_role` | agrees government has a role in affordable housing |
| `hs_affordable_housing_gov_no_role`  | opposes government role in affordable housing      |
| `hs_gentrification_support`          | supports gentrification                            |
| `hs_gentrification_oppose`           | opposes gentrification                             |
| `hs_new_home_buyer`                  | recently bought a home                             |
| `hs_any_home_buyer`                  | has ever bought a home                             |

**taxes** — Tax cuts, gas tax, social security tax, minimum wage, fiscal ideology

| Column                                    | Meaning                                |
| ----------------------------------------- | -------------------------------------- |
| `hs_tax_cuts_support`                     | supports tax cuts                      |
| `hs_tax_cuts_oppose`                      | opposes tax cuts                       |
| `hs_gas_tax_support`                      | supports the gas tax                   |
| `hs_gas_tax_oppose`                       | opposes the gas tax                    |
| `hs_social_security_tax_increase_support` | supports raising social security taxes |
| `hs_social_security_tax_increase_oppose`  | opposes raising social security taxes  |
| `hs_min_wage_15_increase_support`         | supports raising min wage to $15       |
| `hs_min_wage_15_increase_oppose`          | opposes raising min wage to $15        |
| `hs_ideology_fiscal_conserv`              | fiscally conservative ideology         |
| `hs_ideology_fiscal_liberal`              | fiscally liberal ideology              |

**education** — School choice, school funding, charter schools, teachers union views

| Column                              | Meaning                          |
| ----------------------------------- | -------------------------------- |
| `hs_school_choice_support`          | supports school choice           |
| `hs_school_choice_oppose`           | opposes school choice            |
| `hs_school_funding_more`            | favors more school funding       |
| `hs_school_funding_less`            | favors less school funding       |
| `hs_charter_schools_support`        | supports charter schools         |
| `hs_charter_schools_oppose`         | opposes charter schools          |
| `hs_teachers_union_positive`        | positive view of teachers unions |
| `hs_teachers_union_negative`        | negative view of teachers unions |
| `hs_community_college_free_support` | supports free community college  |
| `hs_community_college_free_oppose`  | opposes free community college   |

**healthcare** — Medicaid expansion, Medicare for All, ACA, family medical leave, opioid policy

| Column                            | Meaning                                         |
| --------------------------------- | ----------------------------------------------- |
| `hs_medicaid_expansion_support`   | supports medicaid expansion                     |
| `hs_medicaid_expansion_oppose`    | opposes medicaid expansion                      |
| `hs_medicare_for_all_support`     | supports Medicare for All                       |
| `hs_medicare_for_all_oppose`      | opposes Medicare for All                        |
| `hs_obamacare_aca_expand`         | supports expanding the ACA                      |
| `hs_obamacare_aca_protect`        | supports protecting ACA                         |
| `hs_obamacare_aca_oppose`         | opposes the ACA                                 |
| `hs_family_medical_leave_support` | supports paid family/medical leave              |
| `hs_family_medical_leave_oppose`  | opposes paid family/medical leave               |
| `hs_opioid_crisis_treat`          | treats opioid crisis as a health issue          |
| `hs_opioid_crisis_enforce`        | treats opioid crisis as a law-enforcement issue |

**climate_energy** — Climate change belief, EVs, solar, fracking, federal lands, Green New Deal

| Column                             | Meaning                                 |
| ---------------------------------- | --------------------------------------- |
| `hs_climate_change_believer`       | believes in human-caused climate change |
| `hs_climate_change_nonbeliever`    | rejects human-caused climate change     |
| `hs_electric_vehicle_likely_buyer` | likely to buy an electric vehicle       |
| `hs_electric_vehicle_not_likely`   | unlikely to buy an electric vehicle     |
| `hs_solar_panel_buyer_yes`         | has bought solar panels                 |
| `hs_solar_panel_buyer_no`          | has not bought solar panels             |
| `hs_pipeline_fracking_support`     | supports pipelines/fracking             |
| `hs_pipeline_fracking_oppose`      | opposes pipelines/fracking              |
| `hs_green_new_deal_support`        | supports the Green New Deal             |
| `hs_green_new_deal_oppose`         | opposes the Green New Deal              |
| `hs_sell_federal_lands_support`    | supports selling federal lands          |
| `hs_sell_federal_lands_oppose`     | opposes selling federal lands           |

**immigration** — Mass deportations, border wall, immigration policy views

| Column                          | Meaning                                |
| ------------------------------- | -------------------------------------- |
| `hs_mass_deporations_support`   | supports mass deportations             |
| `hs_mass_deporations_oppose`    | opposes mass deportations              |
| `hs_mexican_wall_support`       | supports a border wall                 |
| `hs_mexican_wall_oppose`        | opposes a border wall                  |
| `hs_immigration_process_unfair` | sees the immigration process as unfair |
| `hs_immigration_undesirable`    | sees more immigration as undesirable   |

**crime_safety** — Violent crime concern, gun control, police trust, death penalty

| Column                          | Meaning                          |
| ------------------------------- | -------------------------------- |
| `hs_violent_crime_very_worried` | very worried about violent crime |
| `hs_violent_crime_not_worried`  | not worried about violent crime  |
| `hs_gun_control_support`        | supports gun control             |
| `hs_gun_control_oppose`         | opposes gun control              |
| `hs_police_trust_yes`           | trusts the police                |
| `hs_police_trust_no`            | does not trust the police        |
| `hs_death_penalty_support`      | supports the death penalty       |
| `hs_death_penalty_oppose`       | opposes the death penalty        |

**social_issues** — Abortion, same-sex marriage, trans athletes, DEI, religion salience

| Column                         | Meaning                                 |
| ------------------------------ | --------------------------------------- |
| `hs_abortion_pro_choice`       | pro-choice on abortion                  |
| `hs_abortion_pro_life`         | pro-life on abortion                    |
| `hs_same_sex_marriage_support` | supports same-sex marriage              |
| `hs_same_sex_marriage_oppose`  | opposes same-sex marriage               |
| `hs_trans_athlete_yes`         | supports trans athlete participation    |
| `hs_trans_athlete_no`          | opposes trans athlete participation     |
| `hs_dei_support`               | supports DEI initiatives                |
| `hs_dei_oppose`                | opposes DEI initiatives                 |
| `hs_religion_important`        | religion is important in their life     |
| `hs_religion_not_important`    | religion is not important in their life |

**regulation_economy** — Regulation, capitalism, unions, income inequality, infrastructure spending

| Column                                   | Meaning                                     |
| ---------------------------------------- | ------------------------------------------- |
| `hs_regulations_too_harsh`               | sees regulations as too harsh               |
| `hs_regulations_good`                    | sees regulations as good                    |
| `hs_capitalism_believe_sound`            | believes capitalism is fundamentally sound  |
| `hs_capitalism_believe_flawed`           | believes capitalism is fundamentally flawed |
| `hs_unions_beneficial`                   | views unions as beneficial                  |
| `hs_unions_not_beneficial`               | views unions as not beneficial              |
| `hs_income_inequality_serious`           | sees income inequality as a serious problem |
| `hs_income_inequality_no_issue`          | sees income inequality as not a real issue  |
| `hs_infrastructure_funding_fund_more`    | favors more infrastructure funding          |
| `hs_infrastructure_funding_enough_spent` | believes enough is spent on infrastructure  |
