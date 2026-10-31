# Benchmark Comparison: OUEG vs Direct LLM (N=100)

- **Total Evaluated Cases**: 100
- **Ambiguous Cases (Multiple structural ties/candidates)**: 69 (69.0%)
- **Unambiguous Cases**: 31 (31.0%)

## Overall Performance

| Metric | Direct LLM | OUEG (Online Unified Evidence Graph) | Delta (OUEG - Direct) |
|---|---|---|---|
| **Exact Match (EM)** | 58.00% | 52.00% | -6.00% |
| **Semantic EM** | 58.00% | 52.00% | -6.00% |
| **Token F1** | 62.73% | 58.10% | -4.63% |
| **Empty Answer Rate** | 20.00% | 30.00% | +10.00% |
| **Avg Latency (sec)** | 22.12s | 36.98s | +14.87s |

## Ambiguity Breakdown

| Subset | Count | Direct LLM EM | OUEG EM | Direct LLM F1 | OUEG F1 |
|---|---|---|---|---|---|
| **Unambiguous Cases** | 31 | 64.52% | 58.06% | 71.72% | 61.51% |
| **Ambiguous Cases** | 69 | 55.07% | 49.28% | 58.70% | 56.57% |

## Case Inspection: Ambiguous Samples

| ID | Question | Gold Answer | Direct LLM Answer | OUEG Answer | Status / Candidates |
|---|---|---|---|---|---|
| `165d33037a93a87e` | How many meters horizontally has the person who obtained 6741 points in heptathon in Talence leaped ? | **7.48** |  |  | SCORE_COLLISION_TIE |
| `4ad1d3215fb69cd0` | What is the largest city of the home country of the sixth place finisher of the 2012 Chicago Marathon ? | **Mombasa** | Moscow | Moscow | SCORE_COLLISION_TIE |
| `91125ed5fbdba303` | Which plain is the city in Yugoslavia that had a GDP index of 172 located on ? | **Pannonian** | Pannonian Plain | Pannonian Plain | SCORE_COLLISION_TIE |
| `1dce3877f261dfbc` | Which PNP member was elected to the Senate first ? | **Itzamar Peña** | Itzamar Peña | Itzamar Peña | SCORE_COLLISION_TIE |
| `e302099f22fa351c` | What is the capital and largest city of the country whose student has an older sister , Princess Ashi Sonam Dechen Wangchuck ? | **Thimphu** | Thimphu | Thimphu | SCORE_COLLISION_TIE |
| `c21990dc1e6933b6` | Who composed the song performed by Al Jarreau ? | **Dave Brubeck** |  |  | SCORE_COLLISION_TIE |
| `f5de2c3184919462` | Which governor who 's seat is up in 2020 is not a commander-in-chief ? | **Roy Cooper** |  |  | SCORE_COLLISION_TIE |
| `c0b376caebe4cb89` | What was the birth month of the player that went from Carlton to West Coast during the 2007 AFL draft ? | **August** | August | August | SCORE_COLLISION_TIE |
| `4f6047b8db1c80b1` | between the members born January 22 , 1880 and March 20 , 1916 what is the name of the university holding the chapter of the one born earlier ? | **University of Utah** | University of Utah | University of Utah | SCORE_COLLISION_TIE |
| `2b9da4e384687fd3` | What event did a country debut in who had an athlete medal at the 2005 Jeux de la Francophonie ? | **equestrian** | Athletics Marathon |  | SCORE_COLLISION_TIE |
| `4091dd5791ed1d78` | What is the call sign of the station licensed to a city formerly known as Henry 's Station ? | **KCBR** | KCBR | KCBR | SCORE_COLLISION_TIE |
| `1553992ce59467a8` | What town was a band formed who had a single that peaked at number 68 in Australia ? | **Geelong** |  |  | SCORE_COLLISION_TIE |
| `04dae7533cca3989` | What is the name of the company is located in the seventh-largest country by area and the second-most populous country ? | **Dhruva Space** | Dhruva Space | Dhruva Space | SCORE_COLLISION_TIE |
| `5728bdcb0bedc535` | What is the name of the airport in the city that is the most populous urban area in Central America ? | **La Aurora International Airport** | La Aurora International Airport | La Aurora International Airport | SCORE_COLLISION_TIE |
| `d7a13239863ff8e8` | Which two kingdoms came from three kingdoms being joined together in the homeland of Ki-Seong Kim ? | **Silla and Balhae** | Silla and Balhae | Silla and Balhae | SCORE_COLLISION_TIE |
| `b457a25d15286377` | Which river flows through this city that has the largest football stadium in England ? | **the River Thames** | River Thames | Thames | SCORE_COLLISION_TIE |
| `8a0c9f5861500669` | What is the name of the club whose city/town is situated between Kgale and Oodi Hills ? | **Gaborone United** | Botswana Defence Force XI | Gaborone United | SCORE_COLLISION_TIE |
| `d27ec782152ad273` | What is the alternative name for the historic place that is located in the township that was established in 1886 and that has the date listed # 14000426 ? | **Portage Entry Light** |  |  | SCORE_COLLISION_TIE |
| `74aea7a48604f353` | How many more goals did the player who debuted for Sweden , at age 17 , on 6 February 1996 have compared to Julie Fleeting ? | **1** | 1 |  | SCORE_COLLISION_TIE |
| `82882205b91225ed` | Of the athletes that participated in the sport of field hockey , which Pakistani flag bearer participated in the Olympic games in 1968 , 1972 , and 1976 ? | **Abdul Rashid Jr** |  |  | SCORE_COLLISION_TIE |
| `4950879950bb5189` | What year of the member of the Hong Kong films entered the music industry ? | **2007** | 1999 |  | SCORE_COLLISION_TIE |
| `557d012523e6d6e7` | What color is the marble inset in the town with a population of 2,685 ? | **green** | green | green | SCORE_COLLISION_TIE |
| `1e911a9dd9d2677f` | what country submitted a not nominated film that had a director who born 1944 ? | **Cuba** | Cuba | Cuba | SCORE_COLLISION_TIE |
| `fffae048bcb4308d` | In the year the Pro Tour event took place in Paris , on what date did the World Championship conclude ? | **17 August 1997** | 17 August 1997 | 17 August 1997 | SCORE_COLLISION_TIE |
| `acfe4293fab8d45c` | How many national championships did the team that won the competition that is organised every year by EHF ? | **30 national championships** | 30 | 30 | SCORE_COLLISION_TIE |
| `f0c414073dddf010` | What were the sales in millions of the song written and produced by The Smeezingtons ? | **10.2** | 10.2 | 10.2 | SCORE_COLLISION_TIE |
| `ad40926595d1d394` | What is the season year whose winner 's nickname is `` The Brazilians '' ? | **1998-99** | 1998-99 | 1998-99, 1999-00, 2000-01, 2002-03 | SCORE_COLLISION_TIE |
| `13ab4d043d9040bf` | who was the runner-up of the 34th Piala Sumbangsih ? | **Perak** | Perak | Perak | SCORE_COLLISION_TIE |
| `03b74593d042dc96` | In the village that was previously an isolated ranch that housed four families , what was the historic place also known as ? | **Chamblis Hotel** |  |  | SCORE_COLLISION_TIE |
| `9a496b3605b8a158` | What year did the clergy graduate who has ties to one of the thirteen historic counties , a vice-county and a former administrative county of Wales ? | **1724** | 1724 | 1724 | SCORE_COLLISION_TIE |
| `dd013edf891ef6b1` | Where were the Olympics held whem Jocelyn Joseph was the flag bearer for Antigua and Barbuda ? | **Seoul** | Seoul | Seoul | SCORE_COLLISION_TIE |
| `14630625ae470511` | What is the date listed for the church in the city that had a population of 1,465 in 2000 ? | **1856 built 1976 NRHP-listed** | 1887 | 1856 built 1976 NRHP-listed | SCORE_COLLISION_TIE |
| `b459c2cb2ef16781` | When the luchador also known to be a licensed Chiropractor won his prision fatal match , what wager did he took ? | **Hair** | Hair | Hair | SCORE_COLLISION_TIE |
| `743fa36d53b80a75` | Consider the titles in 1929 what is the title name where John Ford directed and starred George OBrien ? | **Salute** | Salute | Salute | SCORE_COLLISION_TIE |
| `336b0c6eabe3b0ee` | What is the name of a third listed museum located in a municipality in the Bernina region in the canton of Grisons ? | **Fondazione Ernesto Conrad** | Fondazione Ernesto Conrad | Fondazione Ernesto Conrad | SCORE_COLLISION_TIE |
| `96071d9f3186a6d0` | What is the club whose previous MLS cup appearance was the inaugural season of Major League Soccer , and whose next MLS cup appearance was in 2010 ? | **Dallas Burn/FC Dallas** |  |  | SCORE_COLLISION_TIE |
| `330785d81c36c0ed` | What 's the village name of the Anglican denomination location that straddles A29 ? | **Ockley** | Ockley |  | SCORE_COLLISION_TIE |
| `c1f49af7526d9ef2` | Who established the school that was the 2nd place winner of the 2002 Head of the River ( Queensland ) ? | **Society of the Sacred Heart** |  |  | SCORE_COLLISION_TIE |
| `f7bbdf4a7ba0bd43` | What is the college of the person who was educated at Ruabon Grammar School ? | **Regent 's Park** | Regent 's Park | Regent's Park College | SCORE_COLLISION_TIE |
| `40fda95a874e6fe5` | What is the name of the keyboardist in the band that formed in London in 2007 and had an album that spent 196 weeks in the UK album charts ? | **Isabella Summers** | Isabella Summers | Isabella Summers | SCORE_COLLISION_TIE |
| `72192864e58282fe` | What city hosted the World Championship in the season that Shouta Yasooka ranked 5th twice ? | **Chiba** | Chiba | Chiba | SCORE_COLLISION_TIE |
| `7913b9d158c57cf6` | what is the sport of the silver medalist born 17 March 1973 ? | **Short track speed skating** | Speed skating | Speed skating | MULTIPLE_STRUCTURAL_CANDIDATES |
| `aa1d42444bf86284` | What was the sequel to the film distributed by the distributor owned by The Walt Disney Company ? | **The Jewel of the Nile** |  | The Jewel of the Nile | SCORE_COLLISION_TIE |
| `6a0f818bd7158b0d` | What is the highest ranking achieved by the champion of recurve archery in 2007 at Dubai in archery ? | **number one** |  |  | SCORE_COLLISION_TIE |
| `1f7e1ba710ad54f2` | For whom was this neighborhood constructed in the 18th century located in the district whose name means old city in Catalan ? | **the Ribera neighborhood** | the residents of the Ribera neighborhood | the residents of the Ribera neighborhood | SCORE_COLLISION_TIE |
| `9bafedf1eec75302` | What is CR 33 's notes location 's identity originated from ? | **Land overflowed by the sea** | Napeague, New York | Napeague, New York | SCORE_COLLISION_TIE |
| `e50c0fc0644c1817` | What is the English title of the film whose director was born on 11 October 1961 ? | **Omar** | Paradise Now | Omar | SCORE_COLLISION_TIE |
| `d051048cd7b013a3` | What is the system of the transmitter in Divis transmitting station in which the operator is wholly owned by ITV plc ? | **DVB-T** | DVB-T | DVB-T | SCORE_COLLISION_TIE |
| `b4c59444af6231ab` | How many people in 2010 lived in the city that is home to Deerbrook Mall ? | **15,133** | 15,133 | 15,133 | MULTIPLE_STRUCTURAL_CANDIDATES |
| `ccbdad20297be087` | The NAIA-affiliated Nebraska school is located how far ( in miles ) from the city of Lincoln ? | **50 miles** | 50 miles |  | SCORE_COLLISION_TIE |
| `7d2cbbdbecead98c` | What was the person who founded the Shamrock Hotel known to be the king of ? | **Wildcatter** | Wildcatters | wildcatters | SCORE_COLLISION_TIE |
| `ad50ce5a5cfdf5d5` | Of the winners in 2005 and 2006 which one was born second ? | **Julius Kiptum Rop** | Julius Kiptum Rop | Julius Kiptum Rop | SCORE_COLLISION_TIE |
| `4b2c14918cc950b7` | How many inhabit the Northern Territory district which contains the Ltyentye Apurte suburb ? | **6,863** | 7093 |  | SCORE_COLLISION_TIE |
| `93ae174fd15b5315` | How many premierships in the AFL Women 's competition has the Club won who drafted a player who won the Brownlow Medal in 2008 ? | **one** | 1 | 1 | SCORE_COLLISION_TIE |
| `61bcf886e23ad52c` | What is the name of the player that plays for the club that entered the AIHL in 2002 ? | **Austin McKenzie** |  | Jonathon Bremner | SCORE_COLLISION_TIE |
| `42542320beed1e31` | In what year did the person in fourth place die ? | **2004** | 2004 | 2004 | SCORE_COLLISION_TIE |
| `ea69e6a660f77973` | Which road goes down the coast of the city that Project Runway contestant Ben Chmura resided in ? | **Bayshore Boulevard** |  |  | SCORE_COLLISION_TIE |
| `fda8b206d9074ed8` | What is the population as of 2017 of the location with 12 stands ? | **14,462** |  |  | SCORE_COLLISION_TIE |
| `64882b33b2a57b75` | In what year was the power station in Balloki completed ? | **2018** | 2018 | 2018 | SCORE_COLLISION_TIE |
| `289de27327c03591` | What is Chris Austin 's city also known as ? | **The Gateway to the North** | Gateway to the North | Gateway to the North | SCORE_COLLISION_TIE |
| `1ca8ffcd3e20e498` | What is the historic place whose city or town is also a regional transportation center , located along U.S . Routes 20 and 65 and the Canadian National and Union Pacific Railroads ? | **Edgewood School of Domestic Arts** |  |  | SCORE_COLLISION_TIE |
| `e9188b67cb402773` | How many people inhabit the metro area of the city that María José González Ginestre is from ? | **1,827,165** | 6791000 |  | SCORE_COLLISION_TIE |
| `0828d6547108aeeb` | How many albums has this singer and song-writer sold , who won this award at the Staples Center in Los Angeles on September 13 , 2000 ? | **20 million albums** | 20 million albums | 20 million | SCORE_COLLISION_TIE |
| `0ccec805fd3393f1` | Which author of the Kamakura period treasures died more recently ? | **Fujiwara no Teika** | Fujiwara no Teika |  | SCORE_COLLISION_TIE |
| `90a96e96bee8325f` | What type of aircraft does an Emmen Air Base-based squadron use that is an American business jet introduced in October , 1994 ? | **Cessna Citation Excel ( Model 560XL )** |  |  | SCORE_COLLISION_TIE |
| `226e3e5cd7ec9f29` | What is the state population rank of the Bay Area city which contains the Charles M. Schulz Museum and Research Center ? | **28th** | 25th25th | 28th | SCORE_COLLISION_TIE |
| `2e7e345278fb495e` | What town was the player born in who was recruited from South Adelaide Football Club to the Western Bulldogs ? | **Goolwa** | Goolwa | Goolwa | SCORE_COLLISION_TIE |
| `83cfa408f168a4b5` | How many recipients of the Nobel Prize have been linked with the university of Anne Treisman ? | **68** | 68 |  | SCORE_COLLISION_TIE |
| `42c80d558887db58` | Of the places in the city that was listed as a town in the 2000 census , which was built for the director of Newberry Cotton Mills ? | **George Mower House** | George Mower House | George Mower House | SCORE_COLLISION_TIE |
