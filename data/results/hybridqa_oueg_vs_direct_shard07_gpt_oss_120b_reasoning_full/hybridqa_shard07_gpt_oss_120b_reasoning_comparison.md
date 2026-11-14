# Benchmark Comparison: OUEG vs Direct LLM (N=200)

- **Total Evaluated Cases**: 200
- **Ambiguous Cases (Multiple structural ties/candidates)**: 149 (74.5%)
- **Unambiguous Cases**: 51 (25.5%)

## Overall Performance

| Metric | Direct LLM | OUEG (Online Unified Evidence Graph) | Delta (OUEG - Direct) |
|---|---|---|---|
| **Exact Match (EM)** | 61.50% | 61.50% | +0.00% |
| **Semantic EM** | 62.00% | 62.00% | +0.00% |
| **Token F1** | 71.43% | 72.47% | +1.04% |
| **Empty Answer Rate** | 3.50% | 1.00% | -2.50% |
| **Avg Latency (sec)** | 6.20s | 38.62s | +32.43s |

## Ambiguity Breakdown

| Subset | Count | Direct LLM EM | OUEG EM | Direct LLM F1 | OUEG F1 |
|---|---|---|---|---|---|
| **Unambiguous Cases** | 51 | 64.71% | 62.75% | 76.03% | 72.78% |
| **Ambiguous Cases** | 149 | 60.40% | 61.07% | 69.86% | 72.37% |

## Case Inspection: Ambiguous Samples

| ID | Ambiguous? | Question | Gold Answer | Direct LLM Answer | OUEG Answer | Status / Candidates |
|---|---|---|---|---|---|---|
| `d48fae1cc1f4318a` | Yes | What is Team # 2 of the Team # 1 that holds the record of the oldest player to have ever played at the World Cup ? | **Angola** | Angola | Angola | SCORE_COLLISION_TIE |
| `c76a280443de2a20` | Yes | What is visible on the eastern end of the peak in the Glarus with a 538 meter drop ? | **Braunwald and Linthal** | a glacier | a glacier | SCORE_COLLISION_TIE |
| `52940168b8d4e009` | Yes | What is the name of the racecourse whose country was first inhabited by modern humans during the Upper Palaeolithic period ? | **Bibury Racecourse** | Abingdon Racecourse | Abingdon Racecourse | SCORE_COLLISION_TIE |
| `5cf0621c46b62dd6` | Yes | Which nation used to possess the county represented by Joshua Runey Beauchamp at the Texas legislature 's 11th congress ? | **Mexico** | Mexico | Mexico | SCORE_COLLISION_TIE |
| `d3335e0ca2b08f9d` | Yes | What is the suburb of the school that enrolled approximately 1,500 students in 2018 ? | **Bossley Park** | Bossley Park | Bossley Park | SCORE_COLLISION_TIE |
| `d56add1552e88211` | Yes | Who won a silver at the games with 377 events in 36 sports and disciplines participated in by 6,554 athletes across the continent ? | **Jainab** | Jainab | No Indonesian silver medalist is recorded for the 1998 Asian Games. | MULTIPLE_STRUCTURAL_CANDIDATES |
| `96daa68247fbab60` | Yes | The city named after Saint Elizabeth of Portugal is located in which municipality ? | **Mexicali** | Mexicali | Mexicali Municipality | SCORE_COLLISION_TIE |
| `16eae0e4921fac90` | Yes | How much land does the main campus of the school whose scientific research papers were ranked # 16 encompass ? | **124-acre** | 124 acre | 124 acres | SCORE_COLLISION_TIE |
| `2a4cf4de305a74a0` | Yes | What well known television show is the actress that co-starred in Tim Reid 's film known for ? | **The Cosby Show** | The Cosby Show | The Cosby Show | SCORE_COLLISION_TIE |
| `7f3cdbbd28d54fc3` | Yes | The person who endorsed Mitt Romney on May 31 , 2012 had what middle name ? | **Davis** | Davis | Davis | SCORE_COLLISION_TIE |
| `47d2f78d75402d50` | Yes | At the end of which war did the city with the company better known as CASL become a colony ? | **First Opium War** | First Opium War | the First Opium War | MULTIPLE_STRUCTURAL_CANDIDATES |
| `c95b2f0a616d61cb` | Yes | What is the town that can watch CBS and possibly lava flowing ? | **Hilo** | Hilo | Hilo | SCORE_COLLISION_TIE |
| `0f2a7691b5065d48` | Yes | What is the Association with RMIT of the person who retired from professional football in August 2011 due to injury ? | **current student** | current student | current student | SCORE_COLLISION_TIE |
| `29e4b61cd021b7ac` | Yes | What is the population of the country that is the seventh-largest country in Africa ? | **15,941,000** | 15,941,000 | 15,941,000 | SCORE_COLLISION_TIE |
| `0eb42eaa73511cb9` | Yes | What is the location of the radio services in which there are either two or three broadcasts per day on weekdays ? | **Kirkwall** | Kirkwall | Kirkwall | SCORE_COLLISION_TIE |
| `6feb1e8b698b7e5f` | Yes | Which region contains the city of KVII-TV ? | **Llano Estacado** | Texas | the Llano Estacado region | SCORE_COLLISION_TIE |
| `19dff6f134512c08` | Yes | Which year did the person with the lowest points in paso doble during the 2010 season of Let 's Dance put out her third record ? | **2018** | 2018 | 2018 | SCORE_COLLISION_TIE |
| `5f6685b9482adb40` | Yes | Who was the mother of the child of the athlete who was called 'Rainy Drinkwater ' in a publicity stunt ? | **Rose-Berthe Pilon** |  | Not mentioned | SCORE_COLLISION_TIE |
| `8968a3960210b3c2` | Yes | Which player tries to grab the ball with their heel for the country to the south of Scotland ? | **Jack Armstrong** | Jack Armstrong | Jack Armstrong | SCORE_COLLISION_TIE |
| `70fe8a6b0b994ccc` | Yes | How many years did it take to build the historic place whose city or town 's population was 4,249 at the 2010 census ? | **11** | 2 years | 2 years | SCORE_COLLISION_TIE |
| `567f6f83e9c538b9` | Yes | Which country in which an isopod species was discovered has a population of over 320 million ? | **United States** | United States | United States | MULTIPLE_STRUCTURAL_CANDIDATES |
| `a251b7c2adb7bbf2` | Yes | What position was the athlete who paved the way for Jamaal Charles to rush for a 1,000 yards in 2009 ? | **FB** | Fullback | fullback | SCORE_COLLISION_TIE |
| `d0708d46c3ac0b64` | Yes | Which exchange was the company of the Chinese person worth $ 13.2 billion listed on in June 2018 ? | **Hong Kong Exchanges and Clearing** | Hong Kong Exchanges and Clearing | Hong Kong Exchanges and Clearing | SCORE_COLLISION_TIE |
| `df34953fd12a6334` | Yes | When was the flag bearer at the centennial Olympic Games born ? | **11 July 1969** | 30 June 1969 | 11 July 1969 | SCORE_COLLISION_TIE |
| `4c9a1a2c643aa06a` | Yes | What is the common name for the animal listed as a member of the largest family in the order Carnivora and sometimes called the big stoat ? | **long-tailed weasel** | long-tailed weasel | Long‑tailed weasel | SCORE_COLLISION_TIE |
| `1b64eedd8d2cced8` | Yes | When was the championship played , the year a Falcon 's player won Rookie of the year ? | **April 8 , 2000** | April 8, 2000 | April 8, 2000 | SCORE_COLLISION_TIE |
| `26d182420019b8cb` | Yes | How many seats are in the stadium where the team formerly located in Lockleaze plays ? | **250** | 250 | 250 | SCORE_COLLISION_TIE |
| `d8c8deb347e17ef7` | Yes | How many wins did the team that lost to the New York Jets of the American Football League in Super Bowl III have ? | **13** | 13 | 13 | SCORE_COLLISION_TIE |
| `ab31f17406dac487` | Yes | Which was the first ride with a thrill level of 5 to open ? | **Professor Delbert 's Frontier Fling** | Professor Delbert 's Frontier Fling | Professor Delbert's Frontier Fling | SCORE_COLLISION_TIE |
| `218c6cec21908f4c` | Yes | Which place in Burnsville has been around for longer ? | **Weston and Gauley Bridge Turnpike** | Weston and Gauley Bridge Turnpike | Weston and Gauley Bridge Turnpike | SCORE_COLLISION_TIE |
| `fcbd2395b5ce017d` | Yes | What is the present location of the treasure , created by the person who is generally considered to have inspired the founding of the Rinpa school of painting ? | **Tokyo National Museum , Tokyo** | Tokyo National Museum, Tokyo | Tokyo National Museum | SCORE_COLLISION_TIE |
| `4485e60f367da7ba` | Yes | Who arranged a small string orchestra for a song on the album that spent 27 weeks at number one on the UK Albums Chart ? | **Mike Leander** | Mike Leander | Mike Leander | MULTIPLE_STRUCTURAL_CANDIDATES |
| `c98bba594b28670f` | Yes | When will construction on the 510 m tower in Qatar restart ? | **January 20 , 2021** | January 20, 2021 | January 20 2021 | SCORE_COLLISION_TIE |
| `2a5b703f8d7fed7d` | Yes | Which athlete had the earliest date of violation ? Is it a Chinese long-distance runner who competed in the 3000 metre steeplechase , or a sprinter from the Ukraine who specializes in the 400 metres ? | **Antonina Yefremova** | Antonina Yefremova | Antonina Yefremova | SCORE_COLLISION_TIE |
| `af318afc315877cb` | Yes | How many copies in total has the album that features the song Trigger sold ? | **over 500,000 copies** | over 500,000 copies | over 500,000 copies worldwide | SCORE_COLLISION_TIE |
| `39e20d29e80a2a1f` | Yes | What kind of institution is the namesake of the NYC neighborhood which contains the Museum at FIT ? | **Hospital** |  | a public college | SCORE_COLLISION_TIE |
| `9b030f07965328b8` | Yes | What is the location whose winner was born on September 17 , 1978 ? | **Georgia** | Georgia | Georgia | SCORE_COLLISION_TIE |
| `4b20662303f007e9` | Yes | What is the full nickname of the club that produced the player who played the most games with the Swans after the 1990 draft ? | **Kangaroos** | the Kangaroos | The Kangaroos | SCORE_COLLISION_TIE |
| `f75af0e00010806c` | Yes | What is the power station that is in the state that shares maritime borders with Singapore to the south and Indonesia to both the west and east ? | **Naluri Ventures Sdn Bhd** | Naluri Ventures Sdn Bhd ( license ended in 2010 ) | Naluri Ventures Sdn Bhd | SCORE_COLLISION_TIE |
| `729190ded61fad93` | Yes | What is the ground of the team whose location 's ZIP code is 21144 ? | **Archbishop Spalding High School** | Archbishop Spalding High School | Archbishop Spalding High School | SCORE_COLLISION_TIE |
| `07e585122af9dc18` | Yes | Which society was centered around the area of the home country of Henry López ? | **Maya** | Maya civilization | Maya civilization | SCORE_COLLISION_TIE |
| `f4d7f3a1e92e7474` | Yes | Bomb Blast was made for a platform that was manufactured by who in the early 1990s ? | **Bit Corporation** | Bit Corporation | Bit Corporation | MULTIPLE_STRUCTURAL_CANDIDATES |
| `86605fd1c768164b` | Yes | What is the school for the winner prior to 1965 , that plays the position that tend to stay at or beyond the top of the crease ? | **St. Lawrence** | St. Lawrence | St. Lawrence | SCORE_COLLISION_TIE |
| `d6c7ab035b14fd00` | Yes | Which location serves more routes ? The place home to the Penn and Drexel campus , or The neighborhood of mostly Victorian , mostly twin homes ? | **University City** | University City | University City | SCORE_COLLISION_TIE |
| `71f98e66f68df7d5` | Yes | When was the place in Uppland that is currently used as a hotel used as a hospital until ? | **1985** | 1985 | 1985 | SCORE_COLLISION_TIE |
| `53092a090407224e` | Yes | What is the rank of the organization whose headquarters country consists of 12 provinces ? | **6** | 6 | 11 | SCORE_COLLISION_TIE |
| `e7d0add9782efc93` | Yes | In which province is this football club based ? | **Mendoza Province** | Buenos Aires Province | Tucumán Province | SCORE_COLLISION_TIE |
| `129aeb365127fad6` | Yes | What is the land area of the nationality whose athlete was elected to a seat in the National Assembly in the 2013 Kenyan general election ? | **580,367 square kilometres ( 224,081 sq mi )** | 580,367 square kilometres | 580,367 square kilometres | SCORE_COLLISION_TIE |
| `ebed67f2f9e23ab0` | Yes | Used for sporting events and concerts , this stadium resides in the world 's southernmost capital of a sovereign state ? | **Westpac Stadium** | Westpac Stadium | Westpac Stadium | SCORE_COLLISION_TIE |
| `b6dcc7a5b6742d9f` | Yes | The Jacob Hiestand House can be found of a state route how many miles long ? | **38.245** | 38.245 miles | 38.245 miles | SCORE_COLLISION_TIE |
| `4219cb13a5586fb8` | Yes | How many football members are in the conference who has expanded eight times since 1981 ? | **22** | 10 | 10 | SCORE_COLLISION_TIE |
| `4d35eaf7e881b958` | Yes | What is the population of the Swain County , North Carolina town containing the Nununyi Mound and Village Site ? | **2,138** | 2,138 | 2,138 | SCORE_COLLISION_TIE |
| `d6e99f47917bbd4b` | Yes | What sport does the brother of the gold medalist in modern pentathlon at the 2012 Summer Olympics participate in ? | **triathlete** | triathlon | triathlon | MULTIPLE_STRUCTURAL_CANDIDATES |
| `da85a646aba54f98` | Yes | How many natural features belong to the type of the site whose municipality 's total land area is 111.52 square kilometres ( 43.06 sq mi ) ? | **3** |  | 0 | SCORE_COLLISION_TIE |
| `2319cb7bf99176f0` | Yes | Where did the director of the 2008 movie study film ? | **Moscow** | Moscow | Moscow | SCORE_COLLISION_TIE |
| `e9b3828d48deaabc` | Yes | How far is this California city , where the 2009 Gatorade Player of the Year came from , located from Los Angeles ? | **190 miles** | 190 miles (310 km) | 190 miles (310 km) | SCORE_COLLISION_TIE |
| `bfe721d779a4512d` | Yes | What is the name of the historical unit whose municipality/city is located in the southern portion of the Pannonian Plain ? | **Petrovaradin Fortress** | Petrovaradin Fortress | Lodine Spa | SCORE_COLLISION_TIE |
| `1e5a5f38d78cd1e6` | Yes | What is the 1952 comments person born as namesake ? | **Prince Philip of Greece and Denmark** | Prince Philip of Greece and Denmark | Prince Philip, Duke of Edinburgh | SCORE_COLLISION_TIE |
| `5ebf8b11226575c3` | Yes | How many seasons did the driver who finished 8th in the 2004 Chinese Grand Prix qualifying round drive in Formula One ? | **ten** | from 2002 to 2008 | 11 | SCORE_COLLISION_TIE |
| `079a8368bdad96b3` | Yes | What is the battalion name for the battalion located at Guantanamo Bay and commanded by the author of the book Rifleman 's Creed ? | **4th Defense Battalion** | 4th Defense Battalion | 4th Defense Battalion | SCORE_COLLISION_TIE |
| `cf2e369659f9eea3` | Yes | What is the name of the 1994 club 's home stadium ? | **The Antonette Tubman Stadium** | Antonette Tubman Stadium | Antonette Tubman Stadium | SCORE_COLLISION_TIE |
| `51ff9f90b66b7a06` | Yes | What is the ship whose flag 's nation is surrounded by the Atlantic Ocean ? | **British Reliance** | British Reliance ( 1928 ) | British Reliance ( 1928 ) | SCORE_COLLISION_TIE |
| `2f813cd800de02c9` | Yes | What is the capacity of the venue that was given the name Spartak Stadium in 1939 ? | **11,200** | 10,060 | 10,060 | SCORE_COLLISION_TIE |
| `f72bdd5c8054b2e6` | Yes | How is Grete related to the third place finisher of the Cross-Country World Cup season that ended on March 14 , 2004 ? | **his wife** | She is his wife. | his wife | SCORE_COLLISION_TIE |
| `f84e40d407c74ed8` | Yes | What was the English title of the fifth highest grossing Indian film ? | **Terms and conditions apply** | Sharato Lagu | Terms and conditions apply | SCORE_COLLISION_TIE |
| `213f9cc9bb8dfef9` | Yes | For which clubs did this professional goal keeper play that competed in this World Cup where a then 17-year-old Pelé debuted ? | **Oldham Athletic and Bolton Wanderers** | Bolton Wanderers | Bolton Wanderers and Oldham Athletic | SCORE_COLLISION_TIE |
| `6941e24db37dc964` | Yes | The hometown of the winner of the 1987 Gatorade Player of the Year award is the seat of which county ? | **Escambia County** | Escambia County | Escambia County | SCORE_COLLISION_TIE |
| `cc4b65a90feddb9d` | Yes | In what year was the church located in the Federal Hill neighborhood of Baltimore built ? | **1860** | 1860 | 1860 | SCORE_COLLISION_TIE |
| `6df98c8239f67ff3` | Yes | What is the capacity for the venue designed by the architects Enrico Del Debbio and Aniballe Vitellozzi ? | **20,000** | 9,000 | 20,000 | SCORE_COLLISION_TIE |
| `483ae1bd5ca2a967` | Yes | The venue with a capacity of 8,000 is located in which district of Munich ? | **Neuhausen-Nymphenburg** | Neuhausen‑Nymphenburg | Neuhausen‑Nymphenburg | SCORE_COLLISION_TIE |
| `60f487192df15ddd` | Yes | What is the middle name of the number 4 draft pick of the 2010 Major League Baseball draft ? | **Anthony** | José | Michael | MULTIPLE_STRUCTURAL_CANDIDATES |
| `c9a7d6effe88f170` | Yes | What did the forward with two stints at SC Bastia play for between those two stints ? | **Lyon** | Lyon | Lyon | SCORE_COLLISION_TIE |
| `7edb2051615e0598` | Yes | The city with the highest percentage of Japanese-American population is in what county ? | **Honolulu** | Honolulu County | Honolulu County | SCORE_COLLISION_TIE |
| `1002c04bc7cfcfe7` | Yes | Where are the headquarters of the supermarket chain with 120 stores in Denmark ? | **Amsterdam** | Amsterdam | Amsterdam | SCORE_COLLISION_TIE |
| `08b661ab08709e1d` | Yes | The silenced Soviet 30mm grenade launcher is manufactured in a Country that is officially known as what ? | **the Union of Soviet Socialist Republics** | Union of Soviet Socialist Republics | Union of Soviet Socialist Republics | SCORE_COLLISION_TIE |
| `313d4d099b776774` | Yes | When was the game that was originally released as a coin-operated arcade game on February 20 , 1987 released ? | **February 2 , 2010** | February 20, 1987 | February 2 , 2010 | SCORE_COLLISION_TIE |
| `aa8e5922577f6442` | Yes | What is the population of the city that contains historic structures that were used to make dye ? | **35,938** | 35,938 | 35,938 | SCORE_COLLISION_TIE |
| `c9943d84a8728595` | Yes | What is the position of the coach who is currently an analyst at the University of Alabama ? | **Offensive coordinator** | Offensive coordinator | Offensive Coordinator | SCORE_COLLISION_TIE |
| `e40fef697ae535c6` | Yes | Where did Pawina Thongsuk 's event take place ? | **Banquet Hall** | Al‑Dana Banquet Hall in Doha | Al‑Dana Banquet Hall in Doha | SCORE_COLLISION_TIE |
| `c8fec00282772d1c` | Yes | How many years has the NFL player named best of 2008 by ESPY competed on the Patriots ? | **20** | 20 | 20 | SCORE_COLLISION_TIE |
| `ce570fb15df9042a` | Yes | Which guest actor who played in 'Live ! with Regis and Kelly ' on January 6th is the youngest ? | **Vinny Guadagnino** | Vinny Guadagnino | Vinny Guadagnino | SCORE_COLLISION_TIE |
| `503e0715f7feb36a` | Yes | How many FM stations does the owner of the news station own ? | **44** | 2 | 2 | SCORE_COLLISION_TIE |
| `f6f09ec02eaa8bb8` | Yes | How many provinces were contained at its inception in the home country of Jessica Rakoczy ? | **four** | four | four | SCORE_COLLISION_TIE |
| `9063c034ac745944` | Yes | What is the elevation of the protected area of the Philippines with the least amount of greater area than Mount Malindang ? | **2,954 meters** | 2,954 meters | 2,954 meters | MULTIPLE_STRUCTURAL_CANDIDATES |
| `60dff9aaa4f8985d` | Yes | What novel is the member famous for who is associated with the tv series that , after the sudden death of its actor , left it in question ? | **A Dog 's Purpose** | 8 Simple Rules for Dating My Teenage Daughter | A Dog’s Purpose | SCORE_COLLISION_TIE |
| `4a82d5b7490cd0a0` | Yes | Who was the winner of the bronze of the event that was not held at Soldier Hollow ? | **Richard Gay** | Richard Gay | Richard Gay | SCORE_COLLISION_TIE |
| `f058b6e0891254c7` | Yes | Which Presbyterian missionary founded the church in a city whose population was 18,867 as of the 2010 census ? | **Sheldon Jackson** |  | Sheldon Jackson | SCORE_COLLISION_TIE |
| `34eca79bb78b486a` | Yes | The Marine Corps . member that was honored for actions performed at the latest date was killed during what battle ? | **Battle of Okinawa** | Battle of Okinawa | Battle of Okinawa | SCORE_COLLISION_TIE |
| `5756cb543820ea3b` | Yes | What is this musical instrument made of that dates back to the imperial dynasty of China that ruled from 618 to 907 ? | **brass or bronze** | brass or bronze | gilt bronze | SCORE_COLLISION_TIE |
| `72b239192ab22f7f` | Yes | Which September 9 , 2000 main event person is youngest ? | **Justice Pain** | Justice Pain | Justice Pain | SCORE_COLLISION_TIE |
| `81e7d510f5b964d5` | Yes | What is the party of the winner who contested from Alangulam ( State Assembly Constituency ) and won the election with votes 88891 ? | **DMK** | DMK | ADMK | SCORE_COLLISION_TIE |
| `5927b7be29f378cb` | Yes | Which major league club did the Yankee that earned 127 runs in 1925 start with ? | **Cleveland Indians** | Cleveland Indians | Cleveland Indians | SCORE_COLLISION_TIE |
| `b1c30605039dcbd4` | Yes | What is the state of the Senator or Representative who did not run for reelection to the State Senate in 2014 ? | **Colorado** | Colorado | Colorado | SCORE_COLLISION_TIE |
| `e845c0b004d56121` | Yes | What is the population of the home country of Elena Pingacheva ? | **146.7 million** | 144 million | 146.7 million | SCORE_COLLISION_TIE |
| `4c267931c04686ac` | Yes | Which person had the most laps led from a winning manufacturer that had two men start the company on November 3 , 1911 with a pole position guy that had a three time champion of the Nascar Gander RV & Outdoors Truck Series ? | **James Buescher** | James Buescher | James Buescher | SCORE_COLLISION_TIE |
| `0abff34a26733632` | Yes | Who was runner-up in the season won by a graduate of Vermont 's Mount Snow Academy ? | **Liu Jiayu** | Liu Jiayu | Liu Jiayu | MULTIPLE_STRUCTURAL_CANDIDATES |
| `8981141529183172` | Yes | What is the area in acres of the airport with the smallest number of proposed weekly departures ? | **7,500** | 2,060 acres | 7,500 acres | SCORE_COLLISION_TIE |
| `50ad066451504835` | Yes | What is the home city of the football club whose stadium has the same capacity as the home stadium of the team named after a tributary of the Maritsa River ? | **Veliko Tarnovo** | Veliko Tarnovo | Veliko Tarnovo | SCORE_COLLISION_TIE |
| `c62da59be06438ef` | Yes | Nathalie Hart played Myka in a 2009 romantic series belonging to what genre ? | **Science fiction** | fantasy science fiction romantic drama | fantasy science fiction romantic drama | MULTIPLE_STRUCTURAL_CANDIDATES |
| `da267c6aeaf319d7` | Yes | Which driver had the most races in a single season and had a team that is one of the oldest surviving ? | **Michael Schumacher** | Michael Schumacher | Michael Schumacher | SCORE_COLLISION_TIE |
| `6aa92779b6e75b6d` | Yes | What year did a player make his debut in the K League season who plays the position that has limited defensive responsibilities ? | **2000** | 2000 | 2000 | SCORE_COLLISION_TIE |
| `701033b2e5299bff` | Yes | Who is the guest co-host of the show whose guest married actress Felicity Huffman in 1997 ? | **Jim Parsons** | Jim Parsons | Jim Parsons | SCORE_COLLISION_TIE |
| `1ae4ed2018014fae` | Yes | How many employees work for the company that is located in a country where there are ten provinces and three territories ? | **6,000** | about 10,000 employees worldwide | 6,000 | SCORE_COLLISION_TIE |
| `371ae04942ba2e09` | Yes | Who did the flag bearer compete with in a sport that developed in British India ? | **Juliette Ah-Wan** |  | Georgie Cupidon | SCORE_COLLISION_TIE |
| `89460c0d91f35d50` | Yes | What is the monogram of the town that is the southernmost town in the state of Colorado ? | **B** | B | B | SCORE_COLLISION_TIE |
| `5a78373d429f76f0` | Yes | The title with the least amount in sales was released in what year ? | **2007** | 2007 | 2007 | SCORE_COLLISION_TIE |
| `846ead00c20a4397` | Yes | What bridge runs by the background of the play in which Martin Sheen portrayed Longshoreman in 1992 ? | **Brooklyn Bridge** | Brooklyn Bridge | Brooklyn Bridge | SCORE_COLLISION_TIE |
| `4b80716c6c686c87` | Yes | What is the name of the propulsion system utilized by the satellite line developed by the company involved with the satellite launched by Telesat Canada ? | **Plasma propulsion system** | chemical, bi‑propellant propulsion system | chemical bi‑propellant propulsion system | SCORE_COLLISION_TIE |
| `a34f9785e4a1685b` | Yes | Gympie Coffee Manufacturing uses a fuel type where they preparation takes how many steps ? | **four** | four | four | SCORE_COLLISION_TIE |
| `3ca0cfaeef7da0ed` | Yes | Who was the writer of the series in which Mackenzie Smith played Rhoda Hellberg in 2012 ? | **Annette Cascone** | Dan Schneider | Dan Schneider | SCORE_COLLISION_TIE |
| `b4097ceb0b475782` | Yes | What year did the city of KOBI get its name ? | **1883** | 1977 | 1976 | SCORE_COLLISION_TIE |
| `644820939ecd7553` | Yes | What group does the garden located in the capital of Ishikawa prefecture belong to ? | **Three Great Gardens of Japan** | Monuments of Japan | Monuments of Japan | SCORE_COLLISION_TIE |
| `b40f8772877a224f` | Yes | How many episodes long was the show in which Michael Sheen played Philippe in 1993 ? | **twelve** | twelve | twelve | MULTIPLE_STRUCTURAL_CANDIDATES |
| `446ebb2adfc7e8b6` | Yes | What is the club of the Champions League in which Atlante of Mexico won the championship ? | **New England Revolution** | Cruz Azul | 2008‑09 CONCACAF Champions League | SCORE_COLLISION_TIE |
| `b1c741735e759f2e` | Yes | What medals did the skier win for the Women 's downhill ? | **Downhill and Alpine combined** | Silver | Silver | SCORE_COLLISION_TIE |
| `0c464945d87e62a4` | Yes | The first French ski racer to win an Olympic gold-medal since Jean-Claude Killy , won it in the Super-G at what ski venue ? | **Nakiska on Mount Allan** | Nakiska | Nakiska | SCORE_COLLISION_TIE |
| `01a0c3f14151b9a1` | Yes | What year does Orson Scott Card 's 1986 novel take place ? | **5270** | 5270 | 5270 | SCORE_COLLISION_TIE |
| `6d4547bfa64ed33b` | Yes | Who is the person whose state takes its name from Thomas West ? | **Richard Bayard** | James Bayard | James Bayard | SCORE_COLLISION_TIE |
| `2474f51cb724eb69` | Yes | In what region does the earliest established school reside in Queensland ? | **Capricorn** | Banana | Banana Region | SCORE_COLLISION_TIE |
| `42ca49423de8d69c` | Yes | What is the middle name of the 1988 Gatorade Player of the Year ? | **Harding** | Foster | None | SCORE_COLLISION_TIE |
| `5ba124fedec8be3b` | Yes | What church in Columbia features octogonal towers ? | **Sidney Park Colored Methodist Episcopal Church** | Sidney Park Colored Methodist Episcopal Church | Sidney Park Colored Methodist Episcopal Church | SCORE_COLLISION_TIE |
| `ec3f3a33ae07ac85` | Yes | The smooth muscle are in the GI system in how many stages of digestion ? | **The process of digestion has three stages** | three | three | SCORE_COLLISION_TIE |
| `bdb985965598deac` | Yes | What specialty coaching position does the 1989 CCHA Most Valuable Player in Tournament hold at the Carolina Hurricanes ? | **goaltending coach** | goaltending coach | goaltending coach | SCORE_COLLISION_TIE |
| `d7da7f2df30f54d1` | Yes | What is the song title whose artist is the lead vocalist of the band N*E*R*D ? | **Happy** | Happy | Happy | SCORE_COLLISION_TIE |
| `70c789b849dc85b8` | Yes | Which series , released in the 90 's , was available to play on the first platform to ship over 100 million units ? | **Mortal Kombat Trilogy** | Mortal Kombat | Mortal Kombat Trilogy | SCORE_COLLISION_TIE |
| `d9cada2ad15e5d89` | Yes | What other name is used by the Greek football club that is based in Central Macedonia , in a city that is home to the Department of Physical Education and Sport Science of the Aristotle University of Thessaloniki ? | **The All-Serres Football Club** | All-Serres Football Club | All‑Serres Football Club | SCORE_COLLISION_TIE |
| `f2f47f2855eac021` | Yes | Which mega mall is located in the same location as the cinema with the smallest number of seats in Johor ? | **Paradigm Mall Johor** | Paradigm Mall Johor | Paradigm Mall Johor | MULTIPLE_STRUCTURAL_CANDIDATES |
| `16ca794764db5e27` | Yes | What 1978 law was passed by the person associated with the state with the largest sub-national economy in the world ? | **Proposition 13** | the Howard Jarvis Taxpayers’ Bill of Rights (California Proposition 13, 1978) | Proposition 13 | SCORE_COLLISION_TIE |
| `29bdda48d568b983` | Yes | Who were the professors who received notability for the award who has helped preserve and expand Americans ' access to important resources ? | **Anna Deavere Smith** | Anna Deavere Smith, Rebecca Goldstein, James McBride (writer) | Anna Deavere Smith, Rebecca Goldstein, James McBride (writer) | SCORE_COLLISION_TIE |
| `a5cf7ceed7e24ed8` | Yes | What position was the oldest driver in 2010 Masters of Formula 3 race ? | **18** | 7 | 7 | SCORE_COLLISION_TIE |
| `b24efbe7ea6ac359` | Yes | After the Oregon State alum developed a social networking service originally sought to help users find class members , he co-founded what other company ? | **RedWeek.com** | RedWeek.com | RedWeek.com | SCORE_COLLISION_TIE |
| `2d0055f8957ffe1b` | Yes | Who was the host country of the tournament in which Les Espoirs were the runner-up ? | **Switzerland** | Switzerland | Switzerland | SCORE_COLLISION_TIE |
| `1d43b807eca41878` | Yes | What is the IATA of the country that is bordered by Syria to the north and east and Israel to the south ? | **BEY** | BEY | BEY | SCORE_COLLISION_TIE |
| `4a49b1cf1e787b5d` | Yes | Which film did the American Jewish actress in Community and Mad Men co-write and produce ? | **Horse Girl** | Horse Girl | Horse Girl | SCORE_COLLISION_TIE |
| `3a7d7eedd20dc123` | Yes | What is the lunar feature named after the English geologist , born 1859 , who specialised in petrology and interpretive petrography ? | **Dorsa Harker** | Dorsa Harker | Dorsa Harker | SCORE_COLLISION_TIE |
| `482ca0bbaad57de2` | Yes | How many titles has the Major League Soccer team managed byBen Olsen in 2010 won ? | **thirteen** | 5 | 5 | SCORE_COLLISION_TIE |
| `4d5ad5092b59880e` | Yes | What are the coordinates of the church whose architectural design is by James Gallier , Sr. , James H. Dakin , and Charles Dakin ? | **30°41′22″N 88°2′37″W / 30.68944°N 88.04361°W / 30.68944 ; -88.04361 ( Government Street Presbyterian Church )** | 30°41′22″N 88°2′37″W | 30.68944° N, 88.04361° W | SCORE_COLLISION_TIE |
| `32f7b946549a9c5d` | Yes | Which Olympics was the runner with a time of 44:59 in the 1926 International Cross Country Championships men 's 14.5 km event second place in 10,000 metres ? | **1920 Summer Olympics** | 1920 Summer Olympics | 1920 Summer Olympics | MULTIPLE_STRUCTURAL_CANDIDATES |
| `8dcffe4b10c32367` | Yes | Who is the brother of the winning driver of the pole position who drives the No . 14 Ford Mustang ? | **Kurt Busch** |  |  | SCORE_COLLISION_TIE |
| `660a7b7682d712ab` | Yes | Who was the older person involved in writing the book from 2000 ? | **Sally Jenkins** | Sally Jenkins | Sally Jenkins | SCORE_COLLISION_TIE |
| `d66178d5cb829b16` | Yes | On which date was this film shown at the Asian Film Festival , which was based on this video game series from the company headed by Yuji Ito ? | **June 25 , 2008** | June 20, 2008 | June 20 and June 25, 2008 | SCORE_COLLISION_TIE |
| `7c3e89b072c6145f` | Yes | Which University of Oregon alumni competed in the Games of the XI Olympiad ? | **Mack Robinson** | Mack Robinson | Mack Robinson | SCORE_COLLISION_TIE |
| `66bd35fd89f24e23` | Yes | On what show does the person that co-hosted with Kelly on January 29th currently appear on ? | **Riverdale** | Live with Kelly and Mark | Live! with Kelly and Mark | SCORE_COLLISION_TIE |
| `126a135d05a6db3d` | Yes | Who hosted the show 1st broadcast in 2007 ? | **Ira Glass** | Ira Glass | Ira Glass | SCORE_COLLISION_TIE |
| `4f53f7d6181309da` | Yes | What is the original chapter of the brother who is a noted legal scholar of the First Amendment and freedom of speech ? | **Alpha Sigma / Oregon** | Alpha Sigma / Oregon | Alpha Sigma / Oregon | SCORE_COLLISION_TIE |
| `985c19aa4f67b9c4` | Yes | What is the full name of the earliest player of the year ? | **Mário Rui Correia Tomás** | Mário Rui Silva | Mário Rui Correia de Araújo | SCORE_COLLISION_TIE |
| `4e89db49264f7e7b` | Yes | How many people have faculty jobs at the post-secondary school attended by Sam Bradford ? | **3,000** | 0 | 0 | SCORE_COLLISION_TIE |
| `1756c3c1dc3b4d94` | Yes | In which year was the extreme role-playing video game with hack and slash game mechanics released ? | **2010** | 2010 | 2010 | SCORE_COLLISION_TIE |
| `c543f8abbe87fc13` | Yes | Of the players listed in the Wingman position , how many are said to have become coaches after retiring as players ? | **2** | 1 | 1 | SCORE_COLLISION_TIE |
