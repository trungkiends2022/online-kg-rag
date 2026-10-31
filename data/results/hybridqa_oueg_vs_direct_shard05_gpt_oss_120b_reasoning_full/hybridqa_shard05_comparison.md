# Benchmark Comparison: OUEG vs Direct LLM (N=200)

- **Total Evaluated Cases**: 200
- **Ambiguous Cases (Multiple structural ties/candidates)**: 139 (69.5%)
- **Unambiguous Cases**: 61 (30.5%)

## Overall Performance

| Metric | Direct LLM | OUEG (Online Unified Evidence Graph) | Delta (OUEG - Direct) |
|---|---|---|---|
| **Exact Match (EM)** | 59.00% | 60.50% | +1.50% |
| **Semantic EM** | 61.00% | 61.50% | +0.50% |
| **Token F1** | 72.50% | 73.42% | +0.92% |
| **Empty Answer Rate** | 0.00% | 0.00% | +0.00% |
| **Avg Latency (sec)** | 6.53s | 26.16s | +19.63s |

## Ambiguity Breakdown

| Subset | Count | Direct LLM EM | OUEG EM | Direct LLM F1 | OUEG F1 |
|---|---|---|---|---|---|
| **Unambiguous Cases** | 61 | 63.93% | 63.93% | 77.85% | 75.65% |
| **Ambiguous Cases** | 139 | 56.83% | 58.99% | 70.14% | 72.44% |

## Case Inspection: Ambiguous Samples

| ID | Ambiguous? | Question | Gold Answer | Direct LLM Answer | OUEG Answer | Status / Candidates |
|---|---|---|---|---|---|---|
| `e81beaea78f5dafa` | Yes | In which season did the athlete born in Offenbach am Main first win the competition ? | **1999-00** | 1999-00 | 1999‑00 | SCORE_COLLISION_TIE |
| `9eb12463294d352d` | Yes | What is the notability of the alumnus who was born on December 17 , 1933 ? | **Wisconsin Supreme Court** | Chief Justice of the Wisconsin Supreme Court | Chief Justice of the Wisconsin Supreme Court | SCORE_COLLISION_TIE |
| `b619a4c8b6e071b3` | Yes | What did the park with a Wild Mouse roller coaster launched on September 15 , 2012 launch in November 2017 ? | **virtual reality roller coaster** | the world's first Lego virtual reality roller coaster | the world’s first Lego virtual reality roller coaster | SCORE_COLLISION_TIE |
| `45dcba90b3a5c860` | Yes | What is the code of the subdivision that had a population of 320,379 as of 2013 ? | **FR-07** | FR-07 | FR-07 | SCORE_COLLISION_TIE |
| `f60e2bbd2b92126f` | Yes | How many acres is the surface of the airport that received 632,993 flyers from the airport in Gimhae in 2018 ? | **8,000** | 1,970 acres | 3,240 acres | SCORE_COLLISION_TIE |
| `afdf4514e54bfb08` | Yes | Who is the newest private university named for ? | **Sir Syed Ahmad Khan** | Sir Syed Ahmad Khan | Sir Syed Ahmad Khan | SCORE_COLLISION_TIE |
| `ed3cca395e0eae72` | Yes | Between the 14 March and the 20 March events , which one 's location has the larger land area ? | **Italy** | Italy | Italy | SCORE_COLLISION_TIE |
| `3832ebd26bede85f` | Yes | At the 2010 census , what was the population of the town that is the end of route CR 7 ? | **1,163** | 1,163 | 1,163 | SCORE_COLLISION_TIE |
| `622030650ca8b40b` | Yes | What is the first year that the oldest active team in the professional division from the northern part of Mexico won ? | **2011** | 2011 | 2011 | SCORE_COLLISION_TIE |
| `75f82e0a6cbb94dc` | Yes | In what year was the 2013 FIBA Europe Men 's Player of the Year born ? | **1982** | 1982 | 1982 | SCORE_COLLISION_TIE |
| `b490f0d4d4b3989b` | Yes | For the shipyard launch in late 1980 , what is the sister ship ? | **ARM Huracán** | ARM Huracán | ARM Huracán | SCORE_COLLISION_TIE |
| `9873570604bca240` | Yes | What institution employs the spouse of the graduate with two listed class years , in different decades , and is notable for studying the past specifically not of the US ? | **the same university** | University of Hawaii at Manoa | University of Hawaii at Manoa | SCORE_COLLISION_TIE |
| `a439d8bf8e6d125f` | Yes | What was the measurement of the oldest incline in Pittsburgh ? | **3 ft 4 in** | 1870 | 1870 | SCORE_COLLISION_TIE |
| `ceabe64c91ae0f1b` | Yes | In which city does the team that changed its name in 2001 plays its home games ? | **Trujillo** | Trujillo | Trujillo | SCORE_COLLISION_TIE |
| `8be479e73db63766` | Yes | What other sport did the bronze medalist in alpine skiing play ? | **Tennis** | speed skating | speed skating | SCORE_COLLISION_TIE |
| `35e4463ff9685e93` | Yes | What year did the empire of Portugal establish the city of Santos Dumont Airport ? | **1565** | 1565 | 1565 | SCORE_COLLISION_TIE |
| `411481c54a8450cc` | Yes | In what year was construction on the building with the greatest capacity finished ? | **2019** | 2019 | 2019 | SCORE_COLLISION_TIE |
| `32cdbb29efc454ff` | Yes | When was a college established in the neighborhood that includes Alphabet Cit ? | **1859** | 1859 | 1859 | SCORE_COLLISION_TIE |
| `e04e2dcdec660e3b` | Yes | The club that won the 1974 THB Champions League is from the capital city or what region ? | **Atsimo-Andrefana region** | Toliara | Atsimo‑Andrefana region | SCORE_COLLISION_TIE |
| `59533fad28cd8151` | Yes | What Lake is a site on the shore of that is in a township that has no significant population centers in the township ? | **Lower Herring** | Lower Herring Lake | Lower Herring Lake | SCORE_COLLISION_TIE |
| `13d25c53d82024f4` | Yes | Name the Romanian county , part of Romania 's Transylvania region , renowned for its Medieval past and featuring also the country 's third highest peak ? | **Brașov** | Brașov | Brașov County | SCORE_COLLISION_TIE |
| `dcedafe32d109937` | Yes | Among the cities inside the Ascope province what is the name of the city that is not located in the agricultural Chicama Valley ? | **Casa Grande** | Ascope | Ascope | SCORE_COLLISION_TIE |
| `0d3baa4887a96cfa` | Yes | The boys ' college founded in 1953 is in which suburb ? | **East Gosford** | East Gosford | East Gosford | SCORE_COLLISION_TIE |
| `773655dc61bff645` | Yes | What year ( s ) did the team who is the most successful team from Brazil as for international titles win the Copa Sudamericana ? | **2012** | 2012 | 2012 | SCORE_COLLISION_TIE |
| `d97b4d2829181c9f` | Yes | What is the format of the station whose studios and administrative offices are at 1921 N. Weber Street in Colorado Springs ? | **Classical** | Classical | Classical | SCORE_COLLISION_TIE |
| `83c76e1ae6a17da5` | Yes | Which archipelago of the Caribbean is the home country of the football club Racing CH in ? | **Greater Antilles** | Greater Antilles | Greater Antilles. | SCORE_COLLISION_TIE |
| `9aee4047616ae3f8` | Yes | What was the ship of type hunt-class , destroyer named after ? | **a fox hunt in Oxfordshire** | a fox hunt in Oxfordshire | a fox hunt in Oxfordshire | SCORE_COLLISION_TIE |
| `3177bdd8b935e45f` | Yes | What highway passes by the airport in Canada that had 168,889 airplanes move in a year ? | **Highway 2** | Highway 2 | Highway 2 | MULTIPLE_STRUCTURAL_CANDIDATES |
| `b8451921cf4e2656` | Yes | What class did the player born on May 28 , 1967 play in ? | **Senior** | Senior | Senior | SCORE_COLLISION_TIE |
| `2bdb9d931ebd7858` | Yes | Of the service with the lowest UHF that uses system DVB-T what what is the investment house that is an owner of the service ? | **Macquarie Bank** | Macquarie Bank | Macquarie Bank | SCORE_COLLISION_TIE |
| `43e9b4420942482d` | Yes | What was the American title of the most known movie which had the person who portrayed Denise Grady in Highlander ? | **Sweating Bullets** | Sweating Bullets | Sweating Bullets | SCORE_COLLISION_TIE |
| `af46d2cb4fe258b1` | Yes | When was the place in Plum Lake built ? | **1928** | 1928 | 1928 | SCORE_COLLISION_TIE |
| `342008954a736845` | Yes | The winner of the 2008 The Crowns was born in what town ? | **Tōkai** | Kagoshima | Kawagoe, Saitama Prefecture. | SCORE_COLLISION_TIE |
| `51b148d6265b2433` | Yes | In what year was the lyricist of `` Jis dil mein basa tha pyaar tera '' born ? | **1924** | 1919 | 1919 | SCORE_COLLISION_TIE |
| `ee0d7e8212a60c8b` | Yes | what was the age of the person whose hometown is the most populous city in the United Arab Emirates ( UAE ) ? | **32** | 32 | 32 | SCORE_COLLISION_TIE |
| `ef7b305cc3383de6` | Yes | What is the nominal gross domestic product in USA currency per person in the hometown of the Torneo Descentralizado club Melgar ? | **10,277** | 10,277 USD | 10,277 USD | SCORE_COLLISION_TIE |
| `10c33f7afdcf8732` | Yes | What is the nationality of the driver that finished second at the 2001 Brazilian Grand Prix ? | **German** | German | German | SCORE_COLLISION_TIE |
| `41e4d6e52d865f4d` | Yes | The game that appeared on the PC-98 is similar to how many other games ? | **2** | two | 2 | SCORE_COLLISION_TIE |
| `eb023128000a9684` | Yes | How many uninterrupted baseball seasons of more wins than losses have happened at the university attended by Todd Moser ? | **19** | 19 | 19 | SCORE_COLLISION_TIE |
| `86d4366a034b883a` | Yes | What event was won by a team who current coach is Carlos Retegui ? | **2014-15 Women 's FIH Hockey World League Final** | 2014-15 Women ’s FIH Hockey World League Final | 2014–15 Women's FIH Hockey World League Final | SCORE_COLLISION_TIE |
| `3c05b315381b304a` | Yes | As of 2018 , who holds the position Korn Chatikavanij was notable for holding ? | **Mr Apisak Tantivorawong** | Somkid Jatusripitak | Prawit Wongsuwon | SCORE_COLLISION_TIE |
| `1fd026d173cb9ef8` | Yes | What is the result of the year whose venue sits atop the Gallery Place rapid transit station ? | **Red 121 , White 167** | Red 121 , White 167 | Red 121 , White 167 | SCORE_COLLISION_TIE |
| `f1e8a6bddf1d9e77` | Yes | What was the cost of building the Ferris wheel the least amount taller than London Eye ? | **57 million yuan** | $25 million | 57 million yuan (≈ $7.3 million) | SCORE_COLLISION_TIE |
| `728fc50e112545b1` | Yes | What is the name of the largest island in an archipelago of the country who had the winner of the 2018 ITU Long Distance Triathlon World Championships ? | **Zealand** | Zealand | Zealand | SCORE_COLLISION_TIE |
| `f44e086b34e35c2a` | Yes | Which two countries of athletes dominated the 1990 tournaments ? | **United States and the Soviet Union** | United States and Soviet Union | United States and Soviet Union | SCORE_COLLISION_TIE |
| `22b6a12fee6d055b` | Yes | Where did the trainer of the most recent winner get his first win ? | **Golden Gate Fields racetrack** | Golden Gate Fields racetrack in the San Francisco Bay Area | Golden Gate Fields racetrack. | SCORE_COLLISION_TIE |
| `702b1e9e25d4925d` | Yes | What is the source of the list that is released three times annually ? | **United Nations** | United Nations World Tourism Organization | United Nations World Tourism Organization | SCORE_COLLISION_TIE |
| `6b69ce92008d8259` | Yes | Which company was based in a province that existed until 31 December 2014 ? | **Officine Ferroviarie Moncenisio** | Officine Ferroviarie Moncenisio | Officine Ferroviarie Moncenisio | SCORE_COLLISION_TIE |
| `46147e0a5ed02fb4` | Yes | What was the athlete 's time who would retire from the sport in 1953 at the age of 24 ? | **50:11** | 50:11 | 50:11 | SCORE_COLLISION_TIE |
| `a8414abddae325f5` | Yes | How many times has this rugby union club that had the player born on 7 May 1981 won the Heineken Cup ? | **four times** | 4 | four | SCORE_COLLISION_TIE |
| `9dfcd380a23e50b8` | Yes | What is the club whose home city is an alpha global city ( as listed by the GaWC ) and the most populous city in Brazil ? | **Corinthians** | São Paulo | São Paulo FC | SCORE_COLLISION_TIE |
| `265a90db03f6e137` | Yes | What is the attested activity of the mint location that was known in ancient times as Ambracia ( Ancient Greek : Ἀμβρακία ) ? | **c. 1204-1271** | c. 1204-1271 | c. 1204‑1271 | SCORE_COLLISION_TIE |
| `d740dcead5f9318c` | Yes | What is the capital of the state whose state animal 's original natural habitat is the floating marshy grasslands of the Keibul Lamjao National Park ? | **Imphal** | Imphal | Imphal | SCORE_COLLISION_TIE |
| `5fc2083fa50d24e1` | Yes | What basketball team was the person associated with who had an award for longtime coaches named after him ? | **Detroit Pistons** | Detroit Pistons | Detroit Pistons | SCORE_COLLISION_TIE |
| `3be79807167fc64a` | Yes | Which school is featured in the Netflix sport series that debuted on July 29 , 2016 ? | **East Mississippi Community College** | East Mississippi Community College | East Mississippi Community College | SCORE_COLLISION_TIE |
| `fb04be4c013399b7` | Yes | What is the place of scenic beauty located in the city formerly called Ujiyamada ? | **Futami Bay** | Futami Bay | Futami Bay 二見浦 Futami ura | SCORE_COLLISION_TIE |
| `6c2223709b6b74e8` | Yes | What is the Constituency whose winner was an Indian trade unionist , politician and Member of Parliament ? | **Madras North** | Madras North | Madras North | SCORE_COLLISION_TIE |
| `433b7b2ab743a368` | Yes | What illustrator co-founded a company that developed a title that takes place in a parallel universe to the visual novel Fate/stay night ? | **Takashi Takeuchi** | Takashi Takeuchi | Takashi Takeuchi | SCORE_COLLISION_TIE |
| `e43c9bc205851958` | Yes | When did the director that has received the second most Goya nominations for Best Director die ? | **26 May 2015** | 26 May 2015 | 26 May 2015 | SCORE_COLLISION_TIE |
| `d0f10aa6129a568c` | Yes | What is the population of the city who was the center of military activities during the imperial era ? | **1,174,209** | 2.089 million | 2.089 million | SCORE_COLLISION_TIE |
| `a90b311f0af71764` | Yes | What is the name of the train whose endpoints ( in a typical year ) lies in a basin in Southern California , adjacent to the Pacific Ocean ? | **Saint** | Sacramento | Sacramento | SCORE_COLLISION_TIE |
| `9f78151cffb788a1` | Yes | What county is the Sweeny Refinery located in ? | **Brazoria County** | Brazoria County | Brazoria County | SCORE_COLLISION_TIE |
| `f710fc18aeb3cdaa` | Yes | What name ( s ) is given to the species that is distinguished by having a single petiole ( no post-petiole ) and a slit-like orifice ? | **Anonychomyrma geinitzi** | Dolichoderinae | Dolichoderinae | SCORE_COLLISION_TIE |
| `ae8b00d37d02253e` | Yes | How many points for championships were gained by the person who finished the qualifying round of the British Grand Prix of 1952 right behind Ken Downing ? | **nine** | 0 | 0 | SCORE_COLLISION_TIE |
| `f40c77ab98cb3b8b` | Yes | What is the nickname of the player who scored 20 goals in the 2010 Chinese Super League ? | **Snake** | El Tigre | El Chino | SCORE_COLLISION_TIE |
| `3479f0d1cc709240` | Yes | What year was the company acquired whose software was the first HTTP server program to combine multithreading , a built-in scripting language , and the pooling of persistent database connections ? | **1994** | 1994 | 1995 | SCORE_COLLISION_TIE |
| `4081682ac5e8b133` | Yes | In what round was the Oklahoma athlete drafted in ? | **second** | second round | second round | SCORE_COLLISION_TIE |
| `8de0d44b4e443dd0` | Yes | The 11th Atlantic Hockey Tournament MVP winner was a player born when ? | **July 26 , 1990** | March 30, 1990 | June 30, 1990 | SCORE_COLLISION_TIE |
| `a2b37f8494caa840` | Yes | What controls minds in the game released on October 25 , 2005 ? | **parasite** | Las Plagas | Las Plagas | SCORE_COLLISION_TIE |
| `630cb8691c82ccd9` | Yes | What is the official name of Patrick Roy 's team ? | **le Club de hockey Canadien** | le Club de hockey Canadien | le Club de hockey Canadien | SCORE_COLLISION_TIE |
| `541d9bbb0344e9a0` | Yes | What fuel does the station located in a town in southern Poland on the Oder River and the historical capital of Upper Silesia use ? | **Coal** | Coal | Coal | SCORE_COLLISION_TIE |
| `ea1a0d72bd2c7d45` | Yes | How many states is this nation made up of , where the former football player and current Player Agent was born ? | **36 states** | 36 | 36 | SCORE_COLLISION_TIE |
| `b3bca324d3d3e0d0` | Yes | David H Cohen was part of the chapter at a university located in what city ? | **New York City** | New York City | New York City | MULTIPLE_STRUCTURAL_CANDIDATES |
| `338ff4cb236909d3` | Yes | Which social network video platform does the program broacast since 1992 on MTV by ViacomCBS now air ? | **Facebook Watch** | Facebook Watch | Facebook Watch | SCORE_COLLISION_TIE |
| `28a30854e89b95d5` | Yes | What is the distribution of the RNAs that are defined as being transcripts with lengths exceeding 200 nucleotides that are not translated into protein ? | **Most eukaryotes** | Eukaryotes | Eukaryotes | SCORE_COLLISION_TIE |
| `2e4366c597bbfb87` | Yes | For the game released after January 24 , 2013 and before February 7 , 2013 , what are the two main characters in the game ? | **Popo and Nana** | Popo and Nana | Popo and Nana | SCORE_COLLISION_TIE |
| `10463163e33f7eff` | Yes | What type of college is administered by World Learning ? | **Master 's university** | private graduate institution | Master’s university | SCORE_COLLISION_TIE |
| `2674455019ef1da3` | Yes | In what type of forest are the monkeys classified by the biologist of German descent biologis ? | **rainforests** | rainforests | rainforests of the western Amazon Basin | SCORE_COLLISION_TIE |
| `c47fd7122a103a24` | Yes | The NBA Northwest Division team that finished with a record of 53-29 ( .646 ) in the 2009-10 season calls what stadium home ? | **Pepsi Center** | Pepsi Center | Pepsi Center | SCORE_COLLISION_TIE |
| `266cd6c2876639c8` | Yes | What country did the athlete represent until 2002 whose event 's qualifying standards were 17.10 m ? | **Cape Verde** | Cape Verde | Cape Verde | MULTIPLE_STRUCTURAL_CANDIDATES |
| `c1aae1590ea30268` | Yes | What city contains the largest reciprocating steam-driven engine ever built in the United States ? | **Iron Mountain** | Iron Mountain | Iron Mountain | SCORE_COLLISION_TIE |
| `ec675df4ce21f9ee` | Yes | Where is the setting of the movie that was released in 2007 ? | **Chennai** | Chennai | Chennai | MULTIPLE_STRUCTURAL_CANDIDATES |
| `7b4ed47d5cbddcbc` | Yes | The 1968 's Austrian Sportswoman of the Year married what man with whom she shared a passion for the same sport that was dominated by a French athlete at the 1968 Winter Olympics ? | **Ernst Scartezzini** | Ernst Scartezzini | Ernst Scartezzini | SCORE_COLLISION_TIE |
| `b1bb9316bd356b9c` | Yes | Which parish houses the historic site that is a replica of an early French fort based upon the original blueprints of 1716 by Sieur Charles Claude Dutisné and company ? | **Natchitoches Parish** | Natchitoches Parish | Natchitoches Parish | SCORE_COLLISION_TIE |
| `808d8b25e1cfc5be` | Yes | What is the full name of the oldest suspended athlete that violated rules in 2010 or later ? | **Ahmed Ibrahim Baday** | Michal Balner | Roxana Elisabeta Bîrcă | SCORE_COLLISION_TIE |
| `4a0a27f222a96624` | Yes | What Highway Gothic typeface is the basis of this digital typeface by a designer who teaches typeface design at the Yale School of Art ? | **Style Type E** | Style Type E | Style Type E | SCORE_COLLISION_TIE |
| `021fd26ee829ad33` | Yes | The 1989 Taiwanese submission for the Academy Award for Best International Feature Film was about the White Terror inflicted by what party ? | **Kuomintang** | Kuomintang (KMT) | the Kuomintang (KMT) | SCORE_COLLISION_TIE |
| `30cb7c98c59e6551` | Yes | What year was the community which contains Billiou-Stillwell-Perine House founded ? | **1661** | 1661 | 1661 | SCORE_COLLISION_TIE |
| `5063e9731f612fd1` | Yes | Which date did this sporting event , in which the winner of three gold medals at the 2002 Asian Games won a silver , begin ? | **November 15** | 15 November | 17 November | MULTIPLE_STRUCTURAL_CANDIDATES |
| `300a6de7dd8e0500` | Yes | What is the Serial/Track of the channel whose programming primarily consists of family dramas , cooking shows , news , and movies ? | **Bhavanjali** | Bhavanjali | Bhavanjali | SCORE_COLLISION_TIE |
| `c82a190ccb92d4dd` | Yes | When did the show featuring Jason Dunstall make a debut ? | **20 May** | 20 May | 20 May | SCORE_COLLISION_TIE |
| `718761ff4adab02b` | Yes | Which family members of the protagonist were killed in the 1973 film set in 1874-1894 ? | **father and brother** | her father and brother | her father and brother | SCORE_COLLISION_TIE |
| `768f87189e7a8343` | Yes | What movie was the actor in during 1978 ? | **Ice Castles** | Ice Castles | Ice Castles | SCORE_COLLISION_TIE |
| `0f6ee27f144efa9d` | Yes | What type of disaster hit the state whose name originates from the Ojibwe word mishigamaa ? | **Wildfire** | Tornado outbreak | Tornado outbreak | SCORE_COLLISION_TIE |
| `8a0ee61be3760ab0` | Yes | How many teams total did the players in the position of HK play for in the Super League ? | **five** | 5 | 2 | SCORE_COLLISION_TIE |
| `f128ffedb07ee8e6` | Yes | Which year did the country that got into the FIFA Confederations Cup of 2001 on the 27th of February in 2000 participate in the World Cup ? | **1986** | 1986 | 1986 | SCORE_COLLISION_TIE |
| `88c9a9da010c9a47` | Yes | Gwaneum Park is located in an area of what population size ? | **450,000** | about 450,000 | about 450,000 | SCORE_COLLISION_TIE |
| `b632fd2dd2ccc58a` | Yes | What is the genre of the movie where the character of Shirley appeared ? | **American comedy film** | comedy | Comedy | SCORE_COLLISION_TIE |
| `a8568934ea87b2bf` | Yes | What is the earliest title made by the producer of the Laurel and Hardy and Our Gang film comedy series . ? | **Ladies Last** | Ladies Last | Ladies Last | SCORE_COLLISION_TIE |
| `0fbf394df032a291` | Yes | How long , in km , is the trail that was made out of the closed section of line for the line that used to have a station called Boorcan ? | **37** | 37 | 37 km | MULTIPLE_STRUCTURAL_CANDIDATES |
| `4811b26a0cf9d05e` | Yes | In what township is the school that was charted in 1996 ? | **Moon Township , PA** | Moon Township | Moon Township, PA | SCORE_COLLISION_TIE |
| `ae9b7e89924854b0` | Yes | The Ukrainian who took a silver medal in a sport that was split into the two disciplines of Freestyle and Greco-Roman , was beat out for the gold by what American contender ? | **Jake Varner** | Jake Varner | Jake Varner | SCORE_COLLISION_TIE |
| `2e31208422042ce8` | Yes | In 2010 at the first International Olympic Committee-sanctioned event held in Southeast Asia , Mohammad Soleimani refused to contend against an Israeli fighter who went on to win the gold in what event ? | **under-48-kilogram** | the under‑48‑kilogram taekwondo event | the under‑48‑kilogram taekwondo event | SCORE_COLLISION_TIE |
| `47e7d8726bbe5c6a` | Yes | Who built these forts located at this site in this city founded by fur traders in the 18th century ? | **French , British and U.S. forces** | the French, British and U.S. forces | the French, the British and U.S. forces | SCORE_COLLISION_TIE |
| `275f454c1c2649f5` | Yes | What school did the player who played for the Cleveland Indians from 1968 to 1972 attend ? | **Arizona State** | Arizona | Arizona | SCORE_COLLISION_TIE |
| `1eddd5100a69d1e4` | Yes | How many from the List of United States Naval Academy alumni were awarded the United States military 's second-highest decoration awarded for valor in combat , established by Act of Congress ( Public Law 65-253 ) and approved on February 4 , 1919 ? | **Four** | 3 | 4 | SCORE_COLLISION_TIE |
| `5a9ce11d604584cd` | Yes | President of a subdivision of the New York State Department of Health and husband of Miss Juliet A. Gavette , received his M.D . from what institute ? | **Columbia University** | College of Physicians and Surgeons ( Columbia University ) | College of Physicians and Surgeons (Columbia University) | SCORE_COLLISION_TIE |
| `850a59fe3f1c2a82` | Yes | How many athletes competed in the Olympics in which Julieta Granada was flag bearer for Paraguay ? | **More than 11,000** | 11,238 | 11,238 | SCORE_COLLISION_TIE |
| `8b0626a39033e6f7` | Yes | Between the Dates July 22 and July 25 inclusive which guest has the latest date of birth ? | **Jayma Mays** | Jeremy Piven | Jayma Mays | MULTIPLE_STRUCTURAL_CANDIDATES |
| `61ac900a1aea9afc` | Yes | What was the name of the organization created by the American woman aviator from Atlanta , Georgia ? | **WASP** | Civil Air Patrol | Civil Air Patrol | SCORE_COLLISION_TIE |
| `14ca0bb885702229` | Yes | Who named this rural locality in the LGA created by the Northern Territory government on 6 September 1985 ? | **W. P. Auld** | the Northern Territory government | the Northern Territory government | SCORE_COLLISION_TIE |
| `ac38821ceffcc313` | Yes | Who currently represents this district that was once represented by this judge and politician born on December 11 , 1810 ? | **Republican Rob Wittman** | Rob Wittman | Rob Wittman | MULTIPLE_STRUCTURAL_CANDIDATES |
| `1bbeb7c89e43dbdb` | Yes | Which publication ranked the wrestler who has won in 5 ladder matches number one in 2002 ? | **Pro Wrestling Illustrated** | Pro Wrestling Illustrated | Pro Wrestling Illustrated | SCORE_COLLISION_TIE |
| `9a687a71ffbf0e2a` | Yes | What Party was the winner that was twice elected to the Lok Sabha ? | **Indian National Congress ( I )** | Indian National Congress | Indian National Congress ( I ) | SCORE_COLLISION_TIE |
| `5cdc8869a06434f6` | Yes | Located in Indianapolis , how many Grands Prix did this season consisted of where the event type usually takes place in the summer or autumn ? | **Twenty** | 20 | twenty | SCORE_COLLISION_TIE |
| `a1dfb1f97357786c` | Yes | Who is an American Internet retailer with a website that offers discounted products each day that was also acquired by one of the world 's most valuable companies ? | **Woot** | Woot | Woot | SCORE_COLLISION_TIE |
| `914a6cbdc4e351fe` | Yes | Which historic site is located in the city with a population of 958 as of the 2000 Census ? | **Sunnyside School** | Sunnyside School | Sunnyside School | SCORE_COLLISION_TIE |
| `87d7f2cbefb5c69e` | Yes | What is the song title whose artist is an American singer , songwriter , dancer , actress , record producer , spokesperson and model ? | **Funhouse** | Funhouse ( 2014D ) / ( 2015D ) /NOW-F | Funhouse | SCORE_COLLISION_TIE |
| `043e4ce38525d8ea` | Yes | What is the name of the museum whose region is a metropolitan area located in the Red River Valley ? | **Royal Winnipeg Rifles Regimental Museum** | Royal Winnipeg Rifles Regimental Museum | Royal Winnipeg Rifles Regimental Museum | SCORE_COLLISION_TIE |
| `a7bafc80d9ca2d86` | Yes | What river runs by the hometown of the Zimbabwe football team the Chicken Inn ? | **Matsheumhlope** | Matsheumhlope River | Matsheumhlope River | SCORE_COLLISION_TIE |
| `8c2437d17bddaac1` | Yes | What is the area in kilometres of a lake situated in the 8th most populous province in China ? | **760** | 760 | 760 | SCORE_COLLISION_TIE |
| `1550e7d56a778e6a` | Yes | How many collections of text are in existence of which the book containing Vedic sacrificial rituals and symbolism is an example ? | **than twenty Brahmanas** | 4 | 4 | SCORE_COLLISION_TIE |
| `f97a93ce5c329440` | Yes | What is the election date of the second Superintendent of Canterbury Province ? | **24 August** | 24 August | 24 August | SCORE_COLLISION_TIE |
| `f91a76ab979a0412` | Yes | Who is primarily credited with creating this TV drama aired on the television network owned by Bell Media ? | **Ilene Chaiken** | Ilene Chaiken | Jeffrey Lieber | SCORE_COLLISION_TIE |
| `ee399f2d2ebcdcac` | Yes | What animal returns yearly to rear offspring in the park near La Pointe ? | **Bald eagles** | Bald eagles | Bald eagles | SCORE_COLLISION_TIE |
| `7d7d663617f02f94` | Yes | After receiving her B.S . from the University of Oregon , what actress went on to play what was originally the voice of reason in an FX comedy created by Rob McElhenney ? | **Kaitlin Olson** | Kaitlin Olson | Kaitlin Olson | SCORE_COLLISION_TIE |
| `6fffda4af8e29a5e` | Yes | The only general listed who fought in additional war to the American Civil War , also fought in the Mexican War , Seminole War , and what other war ? | **Indian Wars** | Indian Wars | Indian Wars | SCORE_COLLISION_TIE |
| `8a92baac4500c54b` | Yes | What location was the twelfth season of the Magic 's event take place that was the main event of a minimum three-day mini-convention ? | **San Francisco** | San Francisco | San Francisco | SCORE_COLLISION_TIE |
| `743c4e765fcd76e5` | Yes | What is the oldest school in the LGA that has a A $ 175.13 million capital ( infrastructure ) budget ? | **Toowoomba Grammar School** | Toowoomba Grammar School | Toowoomba Grammar School | SCORE_COLLISION_TIE |
| `ce33cd0ec0077957` | Yes | Which club currently plays in State league in Tasmania and had a nick name The Blues ? | **North Launceston** | Launceston Football Club | Launceston Football Club | SCORE_COLLISION_TIE |
| `893230ff5afb45b7` | Yes | What is the term describing the people from this state that the prosecuting attorney of Tuscarawas County from 1836 to 1841 once represented in the House ? | **Buckeyes** | Ohioans | Ohioans | SCORE_COLLISION_TIE |
| `1aa0eaf4b4456d24` | Yes | Between 1940 and 1940 , what country 's forces occupied the city that hosted at the earliest date ? | **Japanese** | Japan | Japanese | SCORE_COLLISION_TIE |
| `e58c83eac27bc543` | Yes | How many watts does the oldies station power at ? | **500** | 500 watts | 500 watts | SCORE_COLLISION_TIE |
| `f94685b5873293a1` | Yes | What year was the guest born whose host starred as Inspector Terry English ? | **1977** | 1977 | 1977 | SCORE_COLLISION_TIE |
| `d7761188c1b9c7de` | Yes | When was the district represented by the chairman of the Regina Public School board disolved ? | **1964** | 1964 | 1964 | SCORE_COLLISION_TIE |
| `b6e61772817a7468` | Yes | What is the population of the city that contains a landmark that is also known as John Brown 's Cave ? | **7,289** | 7,289 | 7,289 | SCORE_COLLISION_TIE |
| `761409c5fde0b8cc` | Yes | What is the population of the town where Nakasato Caste resides ? | **11,406** | 9,000 | unknown | SCORE_COLLISION_TIE |
| `4373828a6890f3db` | Yes | What age did the driver who finished at position 6 at the 2005 European Grand Prix qualifier start go-karting ? | **three** | three | three | SCORE_COLLISION_TIE |
| `babc0823fe77e4c0` | Yes | What is the stadium of the club that is owned by the Switzerland Armenian businessmen Vartan Sirmakes ? | **Gyumri City Stadium** | City Stadium ( Abovyan ) | City Stadium ( Abovyan ) | MULTIPLE_STRUCTURAL_CANDIDATES |
