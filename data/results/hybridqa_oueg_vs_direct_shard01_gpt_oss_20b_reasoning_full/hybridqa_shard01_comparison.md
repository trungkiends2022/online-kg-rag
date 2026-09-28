# Benchmark Comparison: OUEG vs Direct LLM (N=200)

- **Total Evaluated Cases**: 200
- **Ambiguous Cases (Multiple structural ties/candidates)**: 138 (69.0%)
- **Unambiguous Cases**: 62 (31.0%)

## Overall Performance

| Metric | Direct LLM | OUEG (Online Unified Evidence Graph) | Delta (OUEG - Direct) |
|---|---|---|---|
| **Exact Match (EM)** | 55.50% | 59.00% | +3.50% |
| **Semantic EM** | 57.00% | 60.50% | +3.50% |
| **Token F1** | 63.07% | 67.78% | +4.70% |
| **Empty Answer Rate** | 6.50% | 6.00% | -0.50% |
| **Avg Latency (sec)** | 14.11s | 27.66s | +13.55s |

## Ambiguity Breakdown

| Subset | Count | Direct LLM EM | OUEG EM | Direct LLM F1 | OUEG F1 |
|---|---|---|---|---|---|
| **Unambiguous Cases** | 62 | 62.90% | 62.90% | 70.46% | 71.88% |
| **Ambiguous Cases** | 138 | 52.17% | 57.25% | 59.76% | 65.94% |

## Case Inspection: Ambiguous Samples

| ID | Ambiguous? | Question | Gold Answer | Direct LLM Answer | OUEG Answer | Status / Candidates |
|---|---|---|---|---|---|---|
| `1120dbac5e6cb313` | Yes | What was the original name of the city with an AFL club that formed in 1989 ? | **York** | Toronto | York | SCORE_COLLISION_TIE |
| `2f82321b166609ee` | Yes | What is the Chinese title of the film whose director was born on 7 March 1926 ? | **梁山伯与祝英台** | 倩女幽魂 | 倩女幽魂 | SCORE_COLLISION_TIE |
| `91420918cb0c5428` | Yes | Which number 4 person died most recently ? | **Ned Hanlon** | Ferdinand Abell |  | SCORE_COLLISION_TIE |
| `939454e489df3d2c` | Yes | Who started the company that publishes the game Mythos ? | **Greg Stafford** |  | Sandy Petersen | SCORE_COLLISION_TIE |
| `3ce8475946b4c4ad` | Yes | How old was the manager of Manchester City when he made his football debut ? | **16** | 16 | 16 | SCORE_COLLISION_TIE |
| `2156839d9b37b5b8` | Yes | What county ( s ) does the railroad system service that operates more than 300 trains daily over 21,400 miles ( 34,000 km ) of track ? | **New York** | New York, Essex, Hudson, New Haven, Mercer | New York, Mercer, Essex, New Haven | SCORE_COLLISION_TIE |
| `dc65729d88d9c4ce` | Yes | How many subscribers does the operator that launched in November 2009 , November 2010 , and March 2011 ? | **9.5 million** | Bell | 9.5 million subscribers | SCORE_COLLISION_TIE |
| `b148284a6b9ca70a` | Yes | What is the location on the branch with the least stations ? | **the grounds of the Belmont Park racetrack** | Belmont Park (seasonal service only) | Belmont Park station | SCORE_COLLISION_TIE |
| `6073767cb2f56f4d` | Yes | How many reside in the home city of Julia Costello ? | **2,168** | 1 | Unknown | SCORE_COLLISION_TIE |
| `1518b9d0da2d3711` | Yes | Where is the mall that contains more than 225 outlets , including food courts , restaurants , family entertainment zones , a multiplex , ice skating rink and bowling alley located ? | **Edapally** | Kochi, Kerala | Edapally, Kochi | SCORE_COLLISION_TIE |
| `0f30605a82278300` | Yes | How many times has the Democratic Party had a female candidate before the year 2000 ? | **5** | 5 | 5 | SCORE_COLLISION_TIE |
| `3ee5648fb62a882b` | Yes | What is the score of the winners who won their only Leinster Senior Football Championship title in 1968 ? | **0-11 ( 11 )** | 3-9 | 3-9 | SCORE_COLLISION_TIE |
| `75799415938a14ab` | Yes | What is the address of the stadium which is one of the ones with 8,000 seating , in a city less than 150 miles from a city in the big apple ? | **100 Philip Aziz Avenue** | 1 Richardson Memorial Stadium, Kingston, Ontario K7L 3B9 | No such stadium | SCORE_COLLISION_TIE |
| `9b19e99e6d489e26` | Yes | The park with a 1913 carousel won what award ? | **Best Food** | Golden Ticket Award | Best Food | SCORE_COLLISION_TIE |
| `6eb93d05154ea22e` | Yes | What country did the first female guest move to when she was six ? | **Australia** |  | New Zealand | SCORE_COLLISION_TIE |
| `17cfafd64f7bc87e` | Yes | When was the second earliest winner born ? | **October 25 , 1966** | November 5, 1971 | October 25, 1966. | SCORE_COLLISION_TIE |
| `fb3b196732928c21` | Yes | The retired British policeman who held the position of Commissioner of Police of the Metropolis from 2005 to 2008 went to what College ? | **Christ Church** | Christ Church | Christ Church | SCORE_COLLISION_TIE |
| `58cc2d00ae0f3100` | Yes | Near what pass is the volcano that last erupted in the Holocene era ? | **Santiam Pass** | Santiam Pass | Santiam Pass | SCORE_COLLISION_TIE |
| `1a568f8db60c95bc` | Yes | What book describes the origin of the subcategory that is within the category that is often based on tales from traditional literature ? | **The Nihon Shoki** | Nihon Shoki | Nihon Shoki | SCORE_COLLISION_TIE |
| `05d8934842b3479c` | Yes | Which of the two plays Anna appeared in in 2003 premiered at a theater that was under the leadership of Artistic Director Lynne Meadow ? | **Drug Buddy** | Drug Buddy | Drug Buddy | SCORE_COLLISION_TIE |
| `045ac9c72d1ea77d` | Yes | What is the team color of the club that played in the championship that was the 4th edition under the current AFC Champions League ? | **green** | green | green | SCORE_COLLISION_TIE |
| `e2225981567a1c30` | Yes | What is the middle name of Li Xuerui 's opponent in the finals of the 2015 Denmark Open ? | **Venkata** | Venkata | Venkata | SCORE_COLLISION_TIE |
| `dfa91dd1a8cb176e` | Yes | What is the lifespan of the victim who was one of the plotters involved in the 20 July Plot ? | **1888-1944 , Berlin** | 4 October 1888 – 21 July 1944 | 1907‑1944 | SCORE_COLLISION_TIE |
| `e11350560e7e5bdd` | Yes | What was the biggest gap between first place finishes for King 's ? | **6** | 6 years | 6 years. | SCORE_COLLISION_TIE |
| `b46e1462b5f1d6c1` | Yes | Which stadium located in the Romsdal Peninsula was designed by Kjell Kosberg ? | **Aker Stadion** | Aker Stadion | Aker Stadion | SCORE_COLLISION_TIE |
| `c5d5f598247dc067` | Yes | For the Song of the year award , what was the first year it 's ceremony took place ? | **1984** | 1984 | 1984 | SCORE_COLLISION_TIE |
| `8d9b6dff1a888a1c` | Yes | Which jurisdiction whose standard tax rate was 21 % is mostly credited to be named after a river ? | **Lithuania** | Lithuania | Lithuania | SCORE_COLLISION_TIE |
| `7edafae1e92e6adf` | Yes | Considering the student that was originally from Westfield , New Jersey , which degree he had at Drew University ? | **MA** | MA | M.A. | SCORE_COLLISION_TIE |
| `fba779a01bbe552d` | Yes | A team that had a drought for 2 seasons won the MLS cup for the second time in what year ? | **2013** | 2017 |  | SCORE_COLLISION_TIE |
| `adaaf6a7270e2c27` | Yes | What was the title of the film ( s ) by the director who is known for directing the blockbuster Bharat ? | **Sultan** |  | Sultan, Tiger Zinda Hai | SCORE_COLLISION_TIE |
| `f2cdfff7abf6cd2e` | Yes | Which lake borders the city in which the 100 metres butterfly was swam in 58.7 on July 24 , 1960 ? | **Lake Erie** | Lake Erie | Lake Erie | SCORE_COLLISION_TIE |
| `0561bf8511f5e100` | Yes | How many times has this ice hockey team won the Euro Hockey Tour that scored a gold during the year when this team whose current head coach is Craig Ramsay won a bronze ? | **seven times** |  | 7 | SCORE_COLLISION_TIE |
| `b455fe5ba8dedc3c` | Yes | What is the nationality of the person to have most recently found a fossil ? | **British** | South Africa | British | SCORE_COLLISION_TIE |
| `2245fc1165573fb4` | Yes | What is the AVE-No . of the range that derives its name from a province of the Roman Empire ? | **25** | 25 | 25 | SCORE_COLLISION_TIE |
| `480d8e720f66f472` | Yes | What architect remodeled the site that is in a town where much of the surrounding area is part of either Little Missouri National Grassland ? | **John Tester** | John Tester | John Tester. | SCORE_COLLISION_TIE |
| `78b0e268a721df37` | Yes | How many churches are in the city with a population of 2,190,209 ? | **7** | 7 | 7 | SCORE_COLLISION_TIE |
| `3ba66eadb210d8d5` | Yes | How many goals were scored by the team whose player was born on 23 January 1984 ? | **22** | 22 | 22 | SCORE_COLLISION_TIE |
| `b78f2582d1fa3057` | Yes | What is the Area of the island that has one of the most densely populated islands in the world ? | **619** | 619 km² | 619 km² | SCORE_COLLISION_TIE |
| `d988727e6d46b168` | Yes | The route that ends in an area that lies on the lower slopes of the North Downs begins in the town that had a population of how many people in 2011 ? | **43,013** | 179,000 | 73,000 | SCORE_COLLISION_TIE |
| `2bd60bb7fbc4ff69` | Yes | Who directed the film from 2010 ? | **Tony Tang** | Tony Tang | Tony Tang | SCORE_COLLISION_TIE |
| `c41e9756ec78ec35` | Yes | What is the nationality of the artist whose untitled seventh studio album was released in May 2019 and reached No . 1 in 14 countries ? | **Germany** | Germany | Germany | SCORE_COLLISION_TIE |
| `ec394404f4f90a8f` | Yes | What was the house in Cass County as station of ? | **Underground Railway** | Underground Railway | Reverend George B. Hitchcock House | SCORE_COLLISION_TIE |
| `52a8cddbced3630e` | Yes | What is the name of the building or complex located in the city 25 km north or Red Deer ? | **Roland Michener House** | Roland Michener House | Roland Michener House | SCORE_COLLISION_TIE |
| `d00587e410e6a6fb` | Yes | What is the best league result for a club who beat another club with paralympic sports ? | **4th** | They finished first in the league. | 4th place in the 1992‑93 season | SCORE_COLLISION_TIE |
| `f37e88a92e40c7aa` | Yes | How many times did the team that Wayne Gretzky played for at his 1000th assist win the Stanley Cup ? | **five** | 5 | 5 | SCORE_COLLISION_TIE |
| `0c82534e9921493b` | Yes | Who was the third place in the UCI Mountain Bike World Cup in which the first place was inducted in the Mountain Bike Hall of Fame in the same year ? | **David Wiens** | David Wiens | David Wiens | SCORE_COLLISION_TIE |
| `b0ea0355737a874d` | Yes | How many home runs did the man who was class of 1958 hit in the MLB ? | **1** | 1 | 1 | SCORE_COLLISION_TIE |
| `811ef6ccf8b65eff` | Yes | What was the month of birth of the winner of bronze in men 's single sculls at the 1908 Olympics ? | **May** | May | May | SCORE_COLLISION_TIE |
| `de93f380b7d515d0` | Yes | What is on the other side of Belle Isle from the province which contains Mistastin ? | **Newfoundland** | Newfoundland | Newfoundland | SCORE_COLLISION_TIE |
| `934caf7caff397a9` | Yes | What was the name ( s ) of the characters in the work that was a coming-of-age novel written by Austrian author Felix Salten ? | **Buttercup** | Buttercup, Primrose | Buttercup, Primrose | SCORE_COLLISION_TIE |
| `ac4f0af604d380f6` | Yes | What are the proposed origins of the mother of Ottoman sultan Murad III ? | **Venetian , Jewish or Greek** | Venetian, Jewish, or Greek origin. | Byzantine Greek — born in Bilecik. | SCORE_COLLISION_TIE |
| `95e0c8f6f99b2d90` | Yes | What was the course that closed in 1970 known as ? | **Frying Pan** | the Frying Pan | Alexandra Park Racecourse | SCORE_COLLISION_TIE |
| `46aefbfa01870c18` | Yes | What service is the officer who was appointed in 2004 by general John D. Altenburg part of ? | **United States Army Reserve** | United States Army | United States Army | SCORE_COLLISION_TIE |
| `0e4c5d479205770f` | Yes | Name the reserve whose campus is one of the 10 general campuses of the University of California system ? | **Philip L. Boyd Deep Canyon Desert Research Center** | Box Springs Reserve |  | SCORE_COLLISION_TIE |
| `07b74b36044202eb` | Yes | What banned substance was taken by the athlete born on 30 May 1959 ? | **Pemoline** | Pemoline | Pemoline | SCORE_COLLISION_TIE |
| `d6caced54e336f12` | Yes | What team is located in the capital and largest city of North Macedonia ? | **Akademija FMP** | MZT Skopje | MZT Skopje | SCORE_COLLISION_TIE |
| `5c193dcf3d1f9440` | Yes | What city was the trainer of the 1967 American Horse of the Year born ? | **Centreville** | Lexington |  | SCORE_COLLISION_TIE |
| `6a0a09db3fbe2628` | Yes | What Grammy nominations were received by the album that sold 196,000 copies in Canada in 2016 ? | **Album of the Year and Best Rap Album** | Album of the Year, Best Rap Album | Album of the Year and Best Rap Album | SCORE_COLLISION_TIE |
| `191e903c909d89d3` | Yes | What was the home town whose degree was conferred after four years of full-time study in one or more areas of business concentrations ? | **Sulphur Springs** |  | Sulphur Springs | SCORE_COLLISION_TIE |
| `8c30ec048ab5bdaf` | Yes | What is the real surname of the guest to appear on the January 12 show ? | **Molinsky** | Molinsky | Molinsky | MULTIPLE_STRUCTURAL_CANDIDATES |
| `4f034a4d6e636889` | Yes | What does the name , with the club that for much of its history it 's home ground was Trekardo Park , play for Ballarat Red Devils in ? | **the National Premier Leagues Victoria Division 1** | MF | Jimmy Downey | SCORE_COLLISION_TIE |
| `210b095cb234293a` | Yes | The largest ship from the United States that was sunk was built by what company ? | **Union Iron Works** | Union Iron Works | Union Iron Works | SCORE_COLLISION_TIE |
| `3ff19af8533baaa4` | Yes | When is the expected completion of the hydroelectric power station whose river flows relatively straight North-South before emptying into the Andaman Sea ? | **? ? ( on hold )** | ? ? ( on hold ) | ? ? (on hold) | SCORE_COLLISION_TIE |
| `c05ba9926feb5729` | Yes | Which activity allowed women to compete in a certain sub-part of the sport , earning Iran 4 extra points ? | **Fencing** | Fencing (women’s foil) |  | SCORE_COLLISION_TIE |
| `989a0e368ea33ca5` | Yes | What is the house in Dalzell also known as ? | **Gaillard-Colclough House** | Gaillard‑Colclough House | the Gaillard‑Colclough House | SCORE_COLLISION_TIE |
| `9b4322d80a88248a` | Yes | The city which headquarters the bank which was established on 25 September 2001 has how many inhabitants ? | **128,624 inhabitants** | 128,624 | 128,624 | MULTIPLE_STRUCTURAL_CANDIDATES |
| `d942e11036d795bc` | Yes | what was the class year of the man born on November 19 , 1851 who found notability in the major general , two-star general officer rank , with the pay grade of O-8 ? | **1873** |  | 1873 | MULTIPLE_STRUCTURAL_CANDIDATES |
| `c1fa9e9499f4b1f6` | Yes | What year was the actor in the international title romanized Kosmos kak predchuvstvie , Meritorious Artist of Russian Federation ? | **1996** | 2005 | 2005 | SCORE_COLLISION_TIE |
| `fb7d4b8c103a099b` | Yes | What is the name of the father whose location is the only Israeli locality managed by a private organization ? | **Acacius** | Acacius | Acacius | SCORE_COLLISION_TIE |
| `e172bd0445a3a9ec` | Yes | What portion of the state which contains Albany live in its most populated city ? | **40%** | New York City | 43% | SCORE_COLLISION_TIE |
| `94587ab9c4f93f1b` | Yes | how many school are located about 160 mi North of brisbane ? | **6** | 6 | 6 | SCORE_COLLISION_TIE |
| `1ca98673eac9ec00` | Yes | who was the brother from the chapter at South Carolina State University ? | **W. Melvin Brown** | W. Melvin Brown | W. Melvin Brown | SCORE_COLLISION_TIE |
| `4f854aeb4f98dcfd` | Yes | What is the full name of the oldest recipient that died in a war ? | **Ernest Edwin Evans** | Ernest Edwin Evans | Merritt A. Edson | SCORE_COLLISION_TIE |
| `b3550375a684a870` | Yes | What is the tracking method of the software that provides DCB to enable app store customers to click and buy apps or in-app content , placing the charge directly onto their mobile phone bill ? | **Mobile ID and Cookies** | Mobile ID and cookies | Mobile ID and cookies. | SCORE_COLLISION_TIE |
| `f4e1153e756888e0` | Yes | What is the name of the speaker from constituency represented by two members of parliament ? | **Sir Thomas Hungerford** | Sir James Pickering | Sir John Cheney | SCORE_COLLISION_TIE |
| `e977b50b006e6675` | Yes | What is the 1993 population estimate of the city that is the second-largest city in Myanmar ? | **885,287** | 885,287 | 885,287 | SCORE_COLLISION_TIE |
| `35d3434cd892a157` | Yes | What county is the Como Cemetery in ? | **Park County** | Park County | Park County | SCORE_COLLISION_TIE |
| `a6d1c26b6533da69` | Yes | What is the Location for the organization that is also known as `` DelPark '' ? | **Stanton** | Stanton, Delaware | Stanton | SCORE_COLLISION_TIE |
| `8af7661b0cc32719` | Yes | What is the area of the Seoul park located in the same district that is home to Konkuk University and Sejong Universityr ? | **23,450㎡** | 593,036㎡ |  | SCORE_COLLISION_TIE |
| `1d27b53619245aa5` | Yes | How many aircraft are operated by the air branch that utilizes aircraft based on the ERJ 145 civil regional jet ? | **566** | 5 | 5 | SCORE_COLLISION_TIE |
| `361acf5dddde8555` | Yes | Which Afro-Cuban religion 's dances shares similar footwork with the dance where Marjan Shaki scored a 34 ? | **Santería** | Santería | Santería | SCORE_COLLISION_TIE |
| `05f66d4698b59650` | Yes | What is the state flower of the smallest state by area ? | **Red Jasmine** | Red Jasmine | Red Jasmine | SCORE_COLLISION_TIE |
| `1e643aabae9db3d2` | Yes | What position was the player whose MLS team rebranded in November 2010 , coinciding with its move to their home stadium ? | **F** |  | F | SCORE_COLLISION_TIE |
| `1173f9ce7055cebf` | Yes | What is the original chapter of the brother born 24 April 1974 ? | **Delta Xi** | Delta Xi | Delta Xi | SCORE_COLLISION_TIE |
| `6bcbcb4663dd3332` | Yes | What is the year of birth of the silver medal winner in men 's horizontal bar gymnastics at the 2009 Mediterranean Games ? | **1974** | 1990 | 1990 | SCORE_COLLISION_TIE |
| `f1b667c1b9eaee84` | Yes | What is the population of the metropolitan area containing the city that holds the Toyota factory ? | **12,491,300** | 14,904,400 | unknown | SCORE_COLLISION_TIE |
| `7b85ba59230b082c` | Yes | Where were the Olympics held when Aleksandr Koreshkov was the flag bearer ? | **Italy** | Turin, Italy | Turin, Italy | SCORE_COLLISION_TIE |
| `91fbf85946305aba` | Yes | What is the ground of the club that was an inaugural member club of the NEAFL competition ? | **Cooke-Murphy Oval** | Cooke-Murphy Oval | Cooke‑Murphy Oval | SCORE_COLLISION_TIE |
| `31ec79a377259f79` | Yes | Starring Irina Petrescu , what Romanian film was submitted but rejected as a nominee for Best Foreign Language Film at the Academy Awards , the same year `` Butch Cassidy and the Sundance Kid '' became one of the highest-grossing films of all time ? | **A Woman for a Season** | A Woman for a Season | A Woman for a Season (Romanian: Răutăciosul adolescent) | SCORE_COLLISION_TIE |
| `fdd28b29ce8fea81` | Yes | Who did the athlete with a silver medal in the women 's giant slalom B1 fight in court ? | **Law School Admission Council** | Law School Admission Council | the Law School Admission Council | MULTIPLE_STRUCTURAL_CANDIDATES |
| `6d2facc8faf9afcb` | Yes | What is the medal won by the athlete who was born February 26 , 1971 ? | **Silver** | Silver | Silver | SCORE_COLLISION_TIE |
| `12d788cb8dc887eb` | Yes | What is the name of the oldest person who served in division with over 2.4 million men and women in service ? | **Joseph Raymond Sarnoski** | Joseph R. Sarnoski | William A. Shomo | SCORE_COLLISION_TIE |
| `8367c5ce66b62bcf` | Yes | For which category was the induction of the athlete who died on November 10 , 1991 ? | **Wrestling** | Wrestling | Professional wrestling | SCORE_COLLISION_TIE |
| `dea6326bc98861ff` | Yes | How much is the library branch 's previous space being sold for in the neighborhood that was renamed for its historic 1920s-era Hollywood Theatre ? | **$ 675,000** | $675,000 | $675,000 | SCORE_COLLISION_TIE |
| `bfe892d180948849` | Yes | What clan still has descendants living in the area it is named after ? | **Mackay** | Mackay | Mackay | SCORE_COLLISION_TIE |
| `c0e2096496f3b911` | Yes | Who wrote the book which inspired the film in which Vanessa Redgrave played Blanche Hudson ? | **Henry Farrell** | Henry Farrell | Henry Farrell | SCORE_COLLISION_TIE |
| `19abd710f9881825` | Yes | Who was the real life child who inspired the film directed by François Truffaut in 1970 ? | **Victor of Aveyron** | Victor of Aveyron | Victor of Aveyron | SCORE_COLLISION_TIE |
| `85f26b512d3d6d89` | Yes | Who wrote the fantasy literature which inspired the 2007 game in which Claudi Black had the role of A'Kanna ? | **Robert E. Howard** | Robert E. Howard | Robert E. Howard | SCORE_COLLISION_TIE |
| `47779af1f41e408a` | Yes | Which team drafted the player who went to college in Hempsead , NY ? | **New York Jets** |  | New York Jets | SCORE_COLLISION_TIE |
| `f67b8b120b82c0c4` | Yes | What fuel is used in the ceramics technology for which Nishimatsuura District is known ? | **wood** | firewood | firewood | SCORE_COLLISION_TIE |
| `8dc5433995966606` | Yes | what is the title of the film by the director born 12/5/1890 ? | **The Return of Frank James** | Leave Her to Heaven |  | SCORE_COLLISION_TIE |
| `4a68bbe9b84fcb9f` | Yes | What is the city that the band that sang Heavy Cross formed in ? | **Searcy** | Searcy | Searcy | SCORE_COLLISION_TIE |
| `68e81d3681b85ac7` | Yes | With in a local government area adjacent to the shores of Port Stephens , Myall Lakes and Wallis Lake and the Pacific Highway and the Lakes Way , what name was originally given to the high school ? | **Forster** | Forster High School | Forster High School | SCORE_COLLISION_TIE |
| `63e0b7016ca100cc` | Yes | What city is the smallest building located in ? | **Valparaiso** | Poughkeepsie | Valparaiso | SCORE_COLLISION_TIE |
| `e73b0253ed015a60` | Yes | Which ocean does the namesake of the homeland of Fatma Dabo go into ? | **Atlantic** | Atlantic Ocean | Atlantic Ocean | SCORE_COLLISION_TIE |
| `124769f43d2e1bff` | Yes | What is the stadium of the club that was awarded the Gold Star for sports merits in 1974 ? | **Dossenina** | Dossenina | Dossenina | SCORE_COLLISION_TIE |
| `bbd11ad6adbed10b` | Yes | When was the film whose co-singer sang `` Pudhu Vellai Mazhai '' released ? | **1987** | 1992 | 1992 | SCORE_COLLISION_TIE |
| `959fcd61e3a5425f` | Yes | What is the full name of the politician that has served the most recently ? | **Angela Dawn Craig** | David Cicilline | Angie Craig | SCORE_COLLISION_TIE |
| `e1d41c4b15f3187e` | Yes | What Tablelands city is known for dairy farming ? | **Malanda** | Malanda | Malanda | SCORE_COLLISION_TIE |
| `66986dac8ca302a3` | Yes | what is the stadium capacity of the club that plays in the Vietnamese National Football Third League and is based a city in Đồng Nai Province , Vietnam , about 30 kilometres ( 20 mi ) east of Hồ Chí Minh City ( formerly Saigon ) ? | **5,000** | 5,000 | 5,000 | SCORE_COLLISION_TIE |
| `73c0be18886ed28d` | Yes | In what year did the city in the largest country in Oceania gain city status ? | **1856** | 1856 | 1856 | SCORE_COLLISION_TIE |
| `1d20d0306faabd57` | Yes | Who is the successor of the building society that was founded in 1890 ? | **Yorkshire Building Society** | Yorkshire Building Society | Yorkshire Building Society | SCORE_COLLISION_TIE |
| `a1278f806e536ae3` | Yes | What was the year of birth of the defender from Jamaica during the 2013 Charlotte Eagles season ? | **1986** | 1990 | 1988 | SCORE_COLLISION_TIE |
| `e987e2347dc36977` | Yes | What was the official name of the Olympics in which a silver medal was won by a Croatian team against the United States in an event that had its thirteenth appearance at the Olympics that year ? | **The Games of the XXV Olympiad** | 1992 Summer Olympics | 1992 Summer Olympics | SCORE_COLLISION_TIE |
| `634687cf5fab6bce` | Yes | The flag bearer for Lithuania at the 2016 Summer Olympics was born in what month ? | **November** | March | March | SCORE_COLLISION_TIE |
| `8144e2a8b8f6e1ff` | Yes | What is the home arena of the opponent of the most recent match ? | **Republican Stadium** | Republican Stadium | Republican Stadium | SCORE_COLLISION_TIE |
| `f50907ea0bc6a4bb` | Yes | How many beds are available in the city named after the only U.S . Senator ever killed in military combat ? | **25** | 25 | 25 | SCORE_COLLISION_TIE |
| `0be924155423a4a4` | Yes | What is the degree of the alumnus who was born on 5 September 1885 ? | **BA Theology ( 3rd )** | BA Theology (3rd) | BA Theology (3rd) | SCORE_COLLISION_TIE |
| `4bc1387d27e7f66e` | Yes | As of 2016 , what was the estimated population of the town where the Kaneda Tile Kiln Site is located ? | **10,888** | 10,888 | 10,888 | SCORE_COLLISION_TIE |
| `d90a5bbe1f87f055` | Yes | How many state cup winners is the team that plays in the league that is the fifth tier soccer competition ? | **six** | 6 | 6 | SCORE_COLLISION_TIE |
| `6cdf9c5585c847ce` | Yes | What is the country of the institution that was founded in 1959 ? | **Morocco** | Morocco | Morocco | SCORE_COLLISION_TIE |
| `8949d55b1e9085ba` | Yes | Makomanai Sekisui Heim Ice Arena is located on which island ? | **Hokkaido** | Hokkaido | Hokkaido | SCORE_COLLISION_TIE |
| `61be8a8d94483bdb` | Yes | For the type of stone located in the Church of the Blessed Virgin of the Assumption , how many survive ? | **roughly 400** | 1 | 400 | SCORE_COLLISION_TIE |
| `75ff049093eb37d9` | Yes | When did the player of the most matches first play for the national team ? | **1994** | 1994 | 1994 | SCORE_COLLISION_TIE |
| `71e9a064c1e72df3` | Yes | What club did the commander of the 7th Arkansas Infantry Regiment run after the war ? | **The Ku Klux Klan** |  |  | SCORE_COLLISION_TIE |
| `604b3ecddc138b02` | Yes | In which town is the landmark named after a nearby hanging tree near ? | **Groveland** | Groveland | Groveland | SCORE_COLLISION_TIE |
| `973523e078267912` | Yes | What 's the French name for the militia for the organization now under the leadership of Dory Chamoun ? | **Lionceaux** | Forces Libanaises |  | SCORE_COLLISION_TIE |
| `1bd21532adc066f0` | Yes | How many historic places in Douglas County are located in the city at the western end of lake Superior ? | **15** | 5 | 15 | SCORE_COLLISION_TIE |
| `ae23fa89a583b2ef` | Yes | Which monarch captured this city in the 16th century where this country of around 1.428 billion citizens in 2017 has a delegation ? | **Ivan the Terrible** | Ivan the Terrible | Ivan the Terrible | SCORE_COLLISION_TIE |
| `ea7b4e1aa3a77671` | Yes | How far is this town in the region of 617,700 residents as of 2018 from Christchurch ? | **50 km** | 180 km north of Christchurch | 180 km | SCORE_COLLISION_TIE |
| `f1bae6a149d18a7e` | Yes | Paris La Défense Arena is an arena in a city that is the capital of what department ? | **Hauts-de-Seine** | Hauts‑de‑Seine | Hauts‑de‑Seine | SCORE_COLLISION_TIE |
| `4e727c7794880fff` | Yes | How many states did the nation that was number three in world biathlon in 1992 divide into in 1993 ? | **two** | 2 | 2 | SCORE_COLLISION_TIE |
| `03c35ed66f2cbb69` | Yes | what was the medal won by the Olympian born July 12 , 1971 ? | **Gold** | Gold | Gold | SCORE_COLLISION_TIE |
| `e4941ae66991b658` | Yes | Which major city is the city of AXA Sports Center 30 kilometers southwest of ? | **Stockholm** | Stockholm | Stockholm | SCORE_COLLISION_TIE |
| `23f885b3bb71871f` | Yes | What writing system is used in the home country of Olena Kostevych ? | **Cyrillic** | Cyrillic | Cyrillic | SCORE_COLLISION_TIE |
| `4bc5d335d60f8be6` | Yes | How many times has the player from the Red Wolves football team won the Grey Cup ? | **6** | 6 | 6 | SCORE_COLLISION_TIE |
| `79d017ef11c86c21` | Yes | What was the population of this ward at the 2011 census that was historically in Lancashire within the area that covers the towns and villages of Leigh , and part of Ashton-in-Makerfield ? | **13,486** | 12,000 |  | SCORE_COLLISION_TIE |
| `ad575b3c63388934` | Yes | What is the capacty of the stadium located in the city that is the capital of the Department of Huila ? | **27,000** | 27,000 | 27,000 | MULTIPLE_STRUCTURAL_CANDIDATES |
