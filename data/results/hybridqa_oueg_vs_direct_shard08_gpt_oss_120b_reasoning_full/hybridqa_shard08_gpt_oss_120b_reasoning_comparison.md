# Benchmark Comparison: OUEG vs Direct LLM (N=100)

- **Total Evaluated Cases**: 100
- **Ambiguous Cases (Multiple structural ties/candidates)**: 75 (75.0%)
- **Unambiguous Cases**: 25 (25.0%)

## Overall Performance

| Metric | Direct LLM | OUEG (Online Unified Evidence Graph) | Delta (OUEG - Direct) |
|---|---|---|---|
| **Exact Match (EM)** | 55.00% | 64.00% | +9.00% |
| **Semantic EM** | 55.00% | 64.00% | +9.00% |
| **Token F1** | 67.48% | 77.07% | +9.59% |
| **Empty Answer Rate** | 0.00% | 1.00% | +1.00% |
| **Avg Latency (sec)** | 6.48s | 21.67s | +15.19s |

## Ambiguity Breakdown

| Subset | Count | Direct LLM EM | OUEG EM | Direct LLM F1 | OUEG F1 |
|---|---|---|---|---|---|
| **Unambiguous Cases** | 25 | 56.00% | 68.00% | 73.64% | 81.20% |
| **Ambiguous Cases** | 75 | 54.67% | 62.67% | 65.43% | 75.70% |

## Case Inspection: Ambiguous Samples

| ID | Ambiguous? | Question | Gold Answer | Direct LLM Answer | OUEG Answer | Status / Candidates |
|---|---|---|---|---|---|---|
| `46529434352198b2` | Yes | Who is the owner of the only radio in vancouver that has in its format the genre of popular music that takes its roots from genres such as American folk music ? | **Jim Pattison Group** | Jim Pattison Group | Jim Pattison Group | SCORE_COLLISION_TIE |
| `d06f10a544f875f4` | Yes | What was the first name nickname of the member from the electorate which was represented by 21 members of parliament ? | **Nabob** | Jack | Nabob | SCORE_COLLISION_TIE |
| `ed0725d86d993422` | Yes | What asteroids was discovered on 14 September 1951 and is the same type that exploded over the city of Chelyabinsk ? | **Geographos** | 1620 Geographos | 1620 Geographos | SCORE_COLLISION_TIE |
| `e8afdd30d2d89a3e` | Yes | Which host facility has an installation where pilots practice landing on aircraft carriers by flying at night ? | **Marine Corps Auxiliary Landing Field Bogue Field** | Marine Corps Air Station Cherry Point | Marine Corps Air Station Cherry Point | SCORE_COLLISION_TIE |
| `43fa7b21454936c2` | Yes | What is the degree of the alumnus who is the current chairman of travelers insurance europe ? | **BA Mathematics ( 2nd )** | BA Mathematics ( 2nd ) | BA Mathematics ( 2nd ) | SCORE_COLLISION_TIE |
| `c91c16c91b0d6ca4` | Yes | How many goals did the now deceased player score ? | **3** | 5 | 3 | SCORE_COLLISION_TIE |
| `0543d60603dd9510` | Yes | Between the 1983 and 1984 athlete , which one is younger ? | **Oleg Protsenko** | Oleg Protsenko | Oleg Protsenko | SCORE_COLLISION_TIE |
| `572453cdbbe284fd` | Yes | In what state did Luke Murray coach ? | **Ohio** | Ohio | Ohio | SCORE_COLLISION_TIE |
| `2478f20c9df8d72b` | Yes | What year did the region come into effect where the Allier department is located ? | **2016** | 2016 | 2016 | SCORE_COLLISION_TIE |
| `6b6a4b69f4b76808` | Yes | What was the former designation of the line with a service in Bucks County along the Delaware River to Trenton , New Jersey ? | **R7 Trenton** | R7 Trenton | R7 Trenton | MULTIPLE_STRUCTURAL_CANDIDATES |
| `eefd905a8ba3f3c6` | Yes | What year was the state founded who has a city that is 44 kilometers from Makrana Railway station ? | **1949** | 2000 | 1949 | SCORE_COLLISION_TIE |
| `0c64dfeaceb45bfb` | Yes | Which leading goalscorer of the 1952 - 53 season passed away first ? | **Per Jacobsen** | Per Jacobsen | Per Jacobsen | SCORE_COLLISION_TIE |
| `7fa136746ee831f2` | Yes | What medal did the winner of gold in men 's shot put at the 2012 European Athletics Championships win at the 2012 Summer Olympics ? | **silver** | Silver | Silver | SCORE_COLLISION_TIE |
| `14e391275e529f19` | Yes | What is the title whose notes is an American composer and alto saxophonist subtitled ? | **Volume 1** | The Gerry Mulligan Songbook | The Gerry Mulligan Songbook | SCORE_COLLISION_TIE |
| `0e59865a35754170` | Yes | What is the description for the church occupied by Union troops during the Civil War and was built from reclaimed bricks ? | **Gothic Revival** | Gothic Revival | Gothic Revival | SCORE_COLLISION_TIE |
| `d673192ac091066c` | Yes | Of those whose original chapter is San Diego State University , which one has the earliest birth date ? | **John Frederick Dryer** | Kevin Gilbride | Fred Dryer | SCORE_COLLISION_TIE |
| `04dcf2b84f684bc6` | Yes | What was the format of an event also known as GP that took place in a season which was fifth season ? | **Team Limited** | Rochester Draft | Booster Draft | SCORE_COLLISION_TIE |
| `be11678201ebdb98` | Yes | In what state is the company that deals with human resources headquartered ? | **Michigan** | Michigan | Michigan | SCORE_COLLISION_TIE |
| `898ab90b9e4b66ec` | Yes | How many Australia people were born in the month of September ? | **2** | 2 | 2 | SCORE_COLLISION_TIE |
| `c787f84fcdd3c4b8` | Yes | The team clubhouse of the team with the 60th pick is located in which state ? | **Kansas** | Kansas | Kansas | SCORE_COLLISION_TIE |
| `9f7e6b0cef41b986` | Yes | Who won the division four playoff in the year that the club founded in 1880 as St. Mark 's won the division three playoff ? | **Scunthorpe United** | Scunthorpe United | Scunthorpe United F.C. | SCORE_COLLISION_TIE |
| `3ce9d18930ec1039` | Yes | How many have purchased records by the musicians with the single Just Breathe ? | **85 million** | 2 | 2 | SCORE_COLLISION_TIE |
| `418754ed462bf571` | Yes | Which non-European country has its embassy in the district where the Pushkin Museum is located ? | **Austria** | Bangladesh | Bangladesh | SCORE_COLLISION_TIE |
| `58fafc5b00cf4a6c` | Yes | What is the zip code of the area where the Old Arrow Tree can be found ? | **95550** | 95550 | 95550 | SCORE_COLLISION_TIE |
| `d0ac64e19ae33281` | Yes | Since when has this city , which has this station with an average of 102 alightings in 2013 , had the same geographic boundaries as the county surrounding it ? | **1854** | 1854 | 1854 | SCORE_COLLISION_TIE |
| `1a35f7566d439b74` | Yes | The event that took place in a city with an estimated 2017 population of 104,748 , was on what dates ? | **22-23 June 2019** | 22-23 June 2019 | 22‑23 June 2019 | SCORE_COLLISION_TIE |
| `21fb189d0449f8aa` | Yes | What is the raised date of the garrison that hosts the IAA Commercial Vehicles show every two years ? | **19 December 1803** | 19 December 1803 | 19 December 1803 | SCORE_COLLISION_TIE |
| `39f5ba527b9aaa77` | Yes | The extinct language known as Lycian B belongs to a language family believed to be the earliest group of languages to branch off of what family ? | **Indo-European** | Indo‑European family | Indo‑European | SCORE_COLLISION_TIE |
| `7142d80d4b33784b` | Yes | What is the new name of this football club as of 2018 , based in the capital and the largest city of Kenya ? | **Mt Kenya United** | Kariobangi Sharks | Nairobi City Stars | SCORE_COLLISION_TIE |
| `9e247baa055cbb7c` | Yes | Which battle preceded a declaraton of independence of the home country of Luís Jesús ? | **Battle of Ourique** | Battle of Ourique | Battle of Ourique | SCORE_COLLISION_TIE |
| `c9bf8310ba01b701` | Yes | Where did the most recent winner go to high school ? | **Perris High School** | Perris High School in Perris, California | Perris High School | SCORE_COLLISION_TIE |
| `165556cc17b12ac6` | Yes | What company is located in the city whose population was 19,936 as of the 2010 census ? | **AmeriGas** | AmeriGas | AmeriGas | SCORE_COLLISION_TIE |
| `1a9dfbe67122470f` | Yes | What produce is the city containing the historical Santa Cruz landmark of Castro Adobe known for growing ? | **strawberries , apples , lettuce** | strawberries | strawberries, apples, lettuce | SCORE_COLLISION_TIE |
| `1ef4cccc24736a5c` | Yes | What team did New Zealand play in the city featureing the Mount Panorama racetrack ? | **Western Districts** | Western Districts | Western Districts | SCORE_COLLISION_TIE |
| `bb4643294a887907` | Yes | How many disciplines are there in the sport of Salvatore Sanzo ? | **three disciplines** | 3 | 3 | SCORE_COLLISION_TIE |
| `105caa6a130f33aa` | Yes | What are the bridges that connect Cedar Grove Plantation Chapel 's town ? | **The North Causeway and the South Causeway** | the North Causeway and the South Causeway | North Causeway and South Causeway | SCORE_COLLISION_TIE |
| `51a8ab50c42fbc7e` | Yes | On which date was this spacecraft decommissioned , which was built to explore the C-type asteroid composed of primitive carbonaceous material ? | **1 November 2018** | 30 September 2016 | November 1 2018 | SCORE_COLLISION_TIE |
| `e6f86b2d4694890f` | Yes | What is the status of the futsal club that placed 3rd during the season when the team founded on 1981 with one Portuguese Futsal Cup was the runners-up ? | **dissolved** | Coimbrões |  | SCORE_COLLISION_TIE |
| `16660597b4bc469e` | Yes | In what year was the player who won the 2011 and 2019 John Cahill Medal born ? | **1988** | 1988 | 1988 | SCORE_COLLISION_TIE |
| `503bb0e6f85c583a` | Yes | Considering all the movies that have Positions of `` Music Editor '' what is the title name containing a foster male guardian is murdered by an armed felon ? | **Spider-Man** | Spider-Man | Spider‑Man | SCORE_COLLISION_TIE |
| `1465f76282309639` | Yes | What is Alano 's role in the series that was replaced by Panday Kids in its timeslot ? | **Melissa / Flora Venom** | Melissa / Flora Venom | Melissa / Flora Venom | SCORE_COLLISION_TIE |
| `1c95b268b15c5687` | Yes | What people founded the place in Elmore ? | **French** | French colonists | French colonists. | SCORE_COLLISION_TIE |
| `2774580e928235a7` | Yes | What date did the season begin of the school whose team is led by second year head coach Shaheen Holloway ? | **November 27 , 1981** | 1981-82 | November 14, 1981 | SCORE_COLLISION_TIE |
| `4c985f84a4a7c86a` | Yes | When was the channel launched that has the program Panchami ? | **14 April 1993** | 14 April 1993 | 14 April 1993 | SCORE_COLLISION_TIE |
| `3da8a4141cce2e42` | Yes | What is the year of the champion who was officially founded December 24 , 1889 by a group of railway workers ? | **1971** | 1971 | 1971 | SCORE_COLLISION_TIE |
| `b4fc883e3e1fcc37` | Yes | What was the population of the city or town at the 2010 census of the historic place built by Schuster & Jacob ? | **1,614** | 1,614 | 1,614 | SCORE_COLLISION_TIE |
| `5606db4f90bcd732` | Yes | Which city did the conference of Florida State host their 2012 men 's basketball tournament ? | **Atlanta** | Atlanta | Atlanta | SCORE_COLLISION_TIE |
| `2d48768c4dab3834` | Yes | What event is held every Fourth of July at the same track of the 2018 Motocross des Nations ? | **Lucas Oil Pro Motocross Championships** | Lucas Oil Pro Motocross Championships | Lucas Oil Pro Motocross Championships | SCORE_COLLISION_TIE |
| `b40cca6a45ee3483` | Yes | What temple is in the city where the Medical College was established in the year 2019 ? | **Madan Mohan** | Madan Mohan Temple | Madan Mohan Temple | MULTIPLE_STRUCTURAL_CANDIDATES |
| `12ad267438690b49` | Yes | Which century saw the delineation of the present boundaries of the home country of Amass Amankona ? | **1900s** | 20th century | 20th century | SCORE_COLLISION_TIE |
| `9a673b041cc92df3` | Yes | what is the event of the competition that lasted from 6/22-6/25 ? | **Triple Jump** | USA Outdoor Track and Field Championships | Triple jump | SCORE_COLLISION_TIE |
| `2795b8be112cafc5` | Yes | What is the nationality of the parent company of the channel that broadcast Fame Gurukul in 2005 ? | **Japanese** | Japanese | Indian | SCORE_COLLISION_TIE |
| `aacc7a9edca15a6e` | Yes | What is the producer of the film Angrej wife 's name ? | **wife producer Pammi Baweja** | Pammi Baweja | Pammi Baweja | SCORE_COLLISION_TIE |
| `ad56e75f142f70d6` | Yes | What was the personal name of the Emperor whose documents currently reside at Daitōkyū Memorial Library ? | **Liu Qi** | Liu Qi | Liu Qi | SCORE_COLLISION_TIE |
| `b65d12c6aaf5a00e` | Yes | What team did the player who won the 1986 Cy Young Award in the season he was most valuable player ? | **Houston Astros** | Houston Astros | Houston Astros | SCORE_COLLISION_TIE |
| `7684bef8bd1d27e0` | Yes | Of the skaters from the United States , what is the rank for the pair that are a married couple ? | **13** | 13 | 13 | SCORE_COLLISION_TIE |
| `03c97345742b1d85` | Yes | What is the percentage of the religious ethnicity often affiliated with Nahdlatul Ulama , a moderate Indonesian Muslim organization ? | **3.37** | 3.37% | 3.37% | SCORE_COLLISION_TIE |
| `ed3216d29045c665` | Yes | What musician was the person who departed Borussia Dortmund and joined Arsenal on May 23 , 2006 compared to ? | **Mozart** | Mozart | Mozart | SCORE_COLLISION_TIE |
| `c57355847612cbde` | Yes | How many of the flag bearers were born in December ? | **3** | 2 | 2 | SCORE_COLLISION_TIE |
| `3d740378fa17d9b7` | Yes | What is the capital of the country where La Violencia occurred ? | **Bogotá** | Bogotá | Bogotá | SCORE_COLLISION_TIE |
| `68bb583b7da5beb0` | Yes | What type of aircraft was in service in 1939 ? | **troop transport** | Bristol Bombay bomber/transport | Bristol Bombay bomber/transport | SCORE_COLLISION_TIE |
| `e77612e2467afb6c` | Yes | Who attended the school with the baseball team named The Cardinal ? | **Jason Castro** | Jason Castro | Jason Castro | SCORE_COLLISION_TIE |
| `2c1e60c344e2b104` | Yes | Which valley adjoins the city of KAII-TV ? | **Iao** | Iao Valley | Iao Valley | MULTIPLE_STRUCTURAL_CANDIDATES |
| `27432f264c71480d` | Yes | Which county in the province where the high-profile Three Gorges Dam is located at Yichang has the lowest % of China 's Tujia Population ? | **Jianshi** | Wufeng | Wufeng | SCORE_COLLISION_TIE |
| `c7bd84518c9c8d0f` | Yes | What is the denomination of the church that is now redundant and in the care of the Churches Conservation Trust ? | **Church of England** | Church of England | Church of England | SCORE_COLLISION_TIE |
| `6ff41d63828c01f6` | Yes | Which company developed the stealth game released in March 2005 whose OST is done by the English independent record label with a satellite office in Los Angeles ? | **Ubisoft** | Ubisoft Montreal and Ubisoft Milan | Ubisoft Montreal and Ubisoft Milan | SCORE_COLLISION_TIE |
| `2ef7d6d384512734` | Yes | What is the distance from the closest international airport to the middle of the city which contains Cunard Paradise Beach Hotel & Club ? | **16 kilometres** | 16 kilometres (10 mi) | 16 kilometres (10 mi) | SCORE_COLLISION_TIE |
| `435c0d3dbb3690e1` | Yes | Where can the mountain with the largest drop be reached by cable car from ? | **Sörenberg** | Sörenberg | Sörenberg | SCORE_COLLISION_TIE |
| `0db3fd75f85b7890` | Yes | Which publication 's ranking put the person who finished the qualifying round of the French Grand Prix in 1:13.625 in 2001 at 30th out of all F1 drivers ? | **Times Online 's** | Times Online | Times Online | SCORE_COLLISION_TIE |
| `eb225f4dad6ac4b8` | Yes | What is the location of the host from 2006 championship ? | **Antigonish , Nova Scotia , Canada** | St. Francis Xavier X-Women | Antigonish, Nova Scotia, Canada | SCORE_COLLISION_TIE |
| `36460978d9ec102a` | Yes | How many athletes were born in the month of January ? | **2** | 2 | 2 | SCORE_COLLISION_TIE |
| `2779051b15cb84ac` | Yes | In what city was the building located on Chicago Road founded ? | **1835** | Moscow | Moscow | SCORE_COLLISION_TIE |
| `513064a9a8bdef3d` | Yes | What medals were won at the FIS Nordic World Ski Championships by the gold medalist in men 's individual Nordic combined at the 2006 Winter Olympics ? | **silver** | silver medals | silver medals | SCORE_COLLISION_TIE |
| `d8b866999b5bd723` | Yes | What football club is located in the most populous town in the Syunik Province ? | **Gandzasar Stadium** | Gandzasar | Gandzasar | SCORE_COLLISION_TIE |
| `f1a039aa92cccb1a` | Yes | What is the population of the city for the school that opened in 1907 ? | **57,449 people** | Approximately 1,000,000​ | 57,449 | SCORE_COLLISION_TIE |
