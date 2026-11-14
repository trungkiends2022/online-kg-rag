# Benchmark Comparison: OUEG vs Direct LLM (N=200)

- **Total Evaluated Cases**: 200
- **Ambiguous Cases (Multiple structural ties/candidates)**: 139 (69.5%)
- **Unambiguous Cases**: 61 (30.5%)

## Overall Performance

| Metric | Direct LLM | OUEG (Online Unified Evidence Graph) | Delta (OUEG - Direct) |
|---|---|---|---|
| **Exact Match (EM)** | 59.00% | 59.50% | +0.50% |
| **Semantic EM** | 60.50% | 61.50% | +1.00% |
| **Token F1** | 69.07% | 71.59% | +2.51% |
| **Empty Answer Rate** | 1.00% | 0.50% | -0.50% |
| **Avg Latency (sec)** | 6.83s | 22.03s | +15.20s |

## Ambiguity Breakdown

| Subset | Count | Direct LLM EM | OUEG EM | Direct LLM F1 | OUEG F1 |
|---|---|---|---|---|---|
| **Unambiguous Cases** | 61 | 63.93% | 62.30% | 75.70% | 74.79% |
| **Ambiguous Cases** | 139 | 56.83% | 58.27% | 66.16% | 70.18% |

## Case Inspection: Ambiguous Samples

| ID | Ambiguous? | Question | Gold Answer | Direct LLM Answer | OUEG Answer | Status / Candidates |
|---|---|---|---|---|---|---|
| `9a496b3605b8a158` | Yes | What year did the clergy graduate who has ties to one of the thirteen historic counties , a vice-county and a former administrative county of Wales ? | **1724** | 1724 | 1724 | SCORE_COLLISION_TIE |
| `b457a25d15286377` | Yes | Which river flows through this city that has the largest football stadium in England ? | **the River Thames** | River Thames | Thames | SCORE_COLLISION_TIE |
| `c0b376caebe4cb89` | Yes | What was the birth month of the player that went from Carlton to West Coast during the 2007 AFL draft ? | **August** | August | August | SCORE_COLLISION_TIE |
| `2e7e345278fb495e` | Yes | What town was the player born in who was recruited from South Adelaide Football Club to the Western Bulldogs ? | **Goolwa** | Goolwa | Goolwa | SCORE_COLLISION_TIE |
| `d6afa10d69410b0b` | Yes | On the July 22 episode , which guest is Canadian ? | **Caroline Rhea** | Caroline Rhea | Caroline Rhea | SCORE_COLLISION_TIE |
| `02bcd829bff0be92` | Yes | For the army that conflicted with the `` lashkars '' , what year did its soldier die ? | **3 November 1947** | 1947 | 1947 | SCORE_COLLISION_TIE |
| `90234fbe891e7da5` | Yes | What was the fastest time recorded by the athlete nicknamed The Jarrow Arrow ? | **1:43.61** | 1:43.19 | 1:43.19 | SCORE_COLLISION_TIE |
| `6fdf7bb29965f93a` | Yes | In what league does the team that has the highest capacity play in ? | **League 1** | Betfred Championship | Betfred Championship | SCORE_COLLISION_TIE |
| `a53420d5447c662d` | Yes | What is the name of the bridge whose country is a country located mostly in the southern half of South America ? | **Puente Transbordador Presidente Sáenz Peña** | Puente Transbordador Presidente Sáenz Peña | Puente Transbordador Presidente Sáenz Peña | SCORE_COLLISION_TIE |
| `13ab4d043d9040bf` | Yes | who was the runner-up of the 34th Piala Sumbangsih ? | **Perak** | Perak | Perak | SCORE_COLLISION_TIE |
| `91b711c591f2d172` | Yes | What is the address for the High School that has Green & Gold as their School Colors ? | **2040 Dixwell Avenue in Hamden , Connecticut** | 2040 Dixwell Avenue, Hamden, Connecticut | 2040 Dixwell Avenue, Hamden, Connecticut | SCORE_COLLISION_TIE |
| `91125ed5fbdba303` | Yes | Which plain is the city in Yugoslavia that had a GDP index of 172 located on ? | **Pannonian** | Pannonian Plain | Pannonian Plain | SCORE_COLLISION_TIE |
| `906642bd0ef5c13c` | Yes | Who is the alumni with the notability from the private graduate college that consists of one of the nation 's top-ranked public policy schools ? | **W. Page Keeton** | Ramayya Krishnan | Ramayya Krishnan | SCORE_COLLISION_TIE |
| `8a93731bc6d377ff` | Yes | In what province is the city with a digital launch date of December 9 , 2011 ? | **Manitoba** | Manitoba | Manitoba | SCORE_COLLISION_TIE |
| `84e5c28a3dea0842` | Yes | What Academy Award winning director created Daibosatsu tōge : dai-ippen - Kōgen itto-ryū no maki , an actress who appeared in more than 190 films between 1931 and 1961 ? | **Hiroshi Inagaki** | Hiroshi Inagaki, Ranko Hanai | Hiroshi Inagaki and Ranko Hanai | SCORE_COLLISION_TIE |
| `64882b33b2a57b75` | Yes | In what year was the power station in Balloki completed ? | **2018** | 2018 | 2018 | SCORE_COLLISION_TIE |
| `557d012523e6d6e7` | Yes | What color is the marble inset in the town with a population of 2,685 ? | **green** | green | green | SCORE_COLLISION_TIE |
| `18c8dec4d251069f` | Yes | The Pleiku Stadium is in what province of Vietnam ? | **Gia Lai** | Gia Lai Province | Gia Lai Province | SCORE_COLLISION_TIE |
| `82882205b91225ed` | Yes | Of the athletes that participated in the sport of field hockey , which Pakistani flag bearer participated in the Olympic games in 1968 , 1972 , and 1976 ? | **Abdul Rashid Jr** | Abdul Rashid Jr | Mohammad Asad Malik | SCORE_COLLISION_TIE |
| `5728bdcb0bedc535` | Yes | What is the name of the airport in the city that is the most populous urban area in Central America ? | **La Aurora International Airport** | La Aurora International Airport | La Aurora International Airport | SCORE_COLLISION_TIE |
| `4091dd5791ed1d78` | Yes | What is the call sign of the station licensed to a city formerly known as Henry 's Station ? | **KCBR** | KCBR | KCBR | SCORE_COLLISION_TIE |
| `2533b8545f309e03` | Yes | Who is the +71.5 kg winner when the 66.5 kg winner is the one who was born on October 14 , 1990 ? | **Talita Nogueira** | Talita Nogueira | Talita Nogueira | SCORE_COLLISION_TIE |
| `e302099f22fa351c` | Yes | What is the capital and largest city of the country whose student has an older sister , Princess Ashi Sonam Dechen Wangchuck ? | **Thimphu** | Thimphu | Thimphu | SCORE_COLLISION_TIE |
| `b26b70b6e106086a` | Yes | What is the official name of the waterfall with the 18 m ( 59 ft ) artificially created drop ? | **The Prince of Wales Falls** | Prince of Wales Falls | Prince of Wales Falls | SCORE_COLLISION_TIE |
| `ea7abdbe09da70de` | Yes | Which movie got the person who directed the 1974 movie All Screwed Up an Oscar nod for Best Director in 1977 ? | **Seven Beauties** | Seven Beauties | Seven Beauties | SCORE_COLLISION_TIE |
| `b459c2cb2ef16781` | Yes | When the luchador also known to be a licensed Chiropractor won his prision fatal match , what wager did he took ? | **Hair** | Hair | Hair | SCORE_COLLISION_TIE |
| `4b2c14918cc950b7` | Yes | How many inhabit the Northern Territory district which contains the Ltyentye Apurte suburb ? | **6,863** | 6,000 | 6,863 | SCORE_COLLISION_TIE |
| `9be52c95a06e2fb4` | Yes | What is the team name of the college attended by the 2007-08 winner of the Bob Cousy Award ? | **Longhorns** | Texas Longhorns | Texas Longhorns | SCORE_COLLISION_TIE |
| `e636da27d52e0b7d` | Yes | what year was the nomination for the film that was a three-act romantic comedy by French playwright Marivaux ? | **1988** | 1988 | 1988 | SCORE_COLLISION_TIE |
| `fc32dc6ee5eeea22` | Yes | Who was the oldest player to win 3 times at the Lexus Cup ? | **Sophie Gustafson** | Sophie Gustafson | Sophie Gustafson | SCORE_COLLISION_TIE |
| `d5712ff57caa71c2` | Yes | Where is the park featuring the Steadman Heritage Farmstead Museum located ? | **Kingsport** | Kingsport, Tennessee | Kingsport, Tennessee | SCORE_COLLISION_TIE |
| `c27678a00387d484` | Yes | The train Valley Express that road on an American Class I railroad network , ended in what state ? | **California** | California | California | SCORE_COLLISION_TIE |
| `83cfa408f168a4b5` | Yes | How many recipients of the Nobel Prize have been linked with the university of Anne Treisman ? | **68** | 68 | 0 | SCORE_COLLISION_TIE |
| `6e79490f409f2492` | Yes | Which event in which a Swedish competitor won an individual silver medal was contested by 24 competitors from 6 nations ? | **Men 's 10 m platform** | Men’s 10 metre platform | Men’s 10 metre platform | SCORE_COLLISION_TIE |
| `0aab25d0bbb41210` | Yes | When was the first portable game in the franchise released ? | **2012** | 2012 | 2004 | SCORE_COLLISION_TIE |
| `d27ec782152ad273` | Yes | What is the alternative name for the historic place that is located in the township that was established in 1886 and that has the date listed # 14000426 ? | **Portage Entry Light** |  | Keweenaw Waterway Lower Entrance Light | SCORE_COLLISION_TIE |
| `6250b3c37321c56b` | Yes | At which venue did Žana Novaković carry the flag for the second time ? | **Sochi** | Sochi | Sochi | SCORE_COLLISION_TIE |
| `5a8006b811d6d431` | Yes | What is the gestation period of the monkey belonging to the family that is the smallest of the simian primates ? | **145 days** | about 145 days | about 145 days | SCORE_COLLISION_TIE |
| `e515f0ee646f09e5` | Yes | In 2013 , how many registered members were there in the First Nation that is the namesake of the town of Sooke and had land covered by the Douglas treaties North-west of Sooke Inlet ? | **251 registered members** | 251 | 251 | SCORE_COLLISION_TIE |
| `fbbc65b3949238ac` | Yes | How many times did the skater who finished 7th at 1996 Skate Canada International represent Italy at the Winter Olympics ? | **Winter Olympics** | 2 | twice | SCORE_COLLISION_TIE |
| `b7b230475f4c3332` | Yes | What is the name of the current label manager of the label who released the 1953 album of the artist who holds a record of 80 Grammy nominations ? | **Island Records** | Island Records | Island Records | MULTIPLE_STRUCTURAL_CANDIDATES |
| `14630625ae470511` | Yes | What is the date listed for the church in the city that had a population of 1,465 in 2000 ? | **1856 built 1976 NRHP-listed** | 1905 | 1856 built 1976 | SCORE_COLLISION_TIE |
| `e42ab4501e3f1c4b` | Yes | The most recent musical is based on a movie from what year ? | **1994** | 1967 | 1994 | SCORE_COLLISION_TIE |
| `2798b9525f42c47f` | Yes | When was the city that contains the summer home of Henry Gassaway Davis incorporated ? | **1890** | 1890 | 1890 | SCORE_COLLISION_TIE |
| `84f6d699be825fa8` | Yes | What is the name of the athlete whose sport featured 40 LCM events , split evenly between males and females ? | **Camille Muffat** | Yannick Agnel | Yannick Agnel | SCORE_COLLISION_TIE |
| `939d0c8bd0e11dcc` | Yes | What is the chef-lieu of the region with the most communes among the 20 most populous ? | **Lyon** | Lyon | Lyon | SCORE_COLLISION_TIE |
| `f57e916e8dc5a57e` | Yes | What is the address of the church that was designed by Lewis Vulliamy in the Early Gothic Revival architectural style ? | **Kew Road , Richmond TW9 2TN** | Kew Road, Richmond TW9 2TN | Kew Road, Richmond TW9 2TN | SCORE_COLLISION_TIE |
| `72192864e58282fe` | Yes | What city hosted the World Championship in the season that Shouta Yasooka ranked 5th twice ? | **Chiba** | Chiba | Chiba | SCORE_COLLISION_TIE |
| `226e3e5cd7ec9f29` | Yes | What is the state population rank of the Bay Area city which contains the Charles M. Schulz Museum and Research Center ? | **28th** | 30th | 28th | SCORE_COLLISION_TIE |
| `289de27327c03591` | Yes | What is Chris Austin 's city also known as ? | **The Gateway to the North** | Gateway to the North | Gateway to the North | SCORE_COLLISION_TIE |
| `02e3ebd215153d9b` | Yes | What is the name of the actor in the top three listed on the chart and was born 1951 , in Bombay , India ? | **Shahid Kapoor** | Sajid Khan | Sajid Khan | SCORE_COLLISION_TIE |
| `4ad1d3215fb69cd0` | Yes | What is the largest city of the home country of the sixth place finisher of the 2012 Chicago Marathon ? | **Mombasa** | Moscow | Moscow | SCORE_COLLISION_TIE |
| `bedec99a504fe36d` | Yes | Which party had won the general election prior to this meeting that resulted in the constitution with five articles ? | **Sinn Féin** | Sinn Féin | Sinn Féin | SCORE_COLLISION_TIE |
| `34c3f25112c0d074` | Yes | The building in Upstate New York at 391 feet has been suggested as the inspiration of what building ? | **Empire State Building** | Empire State Building | Empire State Building | SCORE_COLLISION_TIE |
| `fffae048bcb4308d` | Yes | In the year the Pro Tour event took place in Paris , on what date did the World Championship conclude ? | **17 August 1997** | 17 August 1997 | 17 August 1997 | SCORE_COLLISION_TIE |
| `6a0f818bd7158b0d` | Yes | What is the highest ranking achieved by the champion of recurve archery in 2007 at Dubai in archery ? | **number one** | Gold | Gold | SCORE_COLLISION_TIE |
| `9bafedf1eec75302` | Yes | What is CR 33 's notes location 's identity originated from ? | **Land overflowed by the sea** | Napeague, New York | Napeague, New York | SCORE_COLLISION_TIE |
| `481d9930f6124d2a` | Yes | Who built the bridge that is in the city that is located approximately halfway between Columbus and Tallahassee , Florida on U.S. Route 27 ? | **J.W . Baughman** | J.W. Baughman | J.W. Baughman | SCORE_COLLISION_TIE |
| `d051048cd7b013a3` | Yes | What is the system of the transmitter in Divis transmitting station in which the operator is wholly owned by ITV plc ? | **DVB-T** | DVB-T | DVB‑T | SCORE_COLLISION_TIE |
| `bbff05702511d184` | Yes | What number pick was the player born on February 28 , 1999 ? | **3** | 3 | 3 | SCORE_COLLISION_TIE |
| `583d7d2b3b3f7351` | Yes | What league was the team that Neil Hlavaty joined on the first of January in 2013 previously a member of ? | **North American Soccer League** | North American Soccer League (NASL) | North American Soccer League | SCORE_COLLISION_TIE |
| `0bf55eeef837fa9c` | Yes | What is the event of the athlete who accomplished a then-World Youth Best of 23.23 m. in 2010 ? | **Boys ' Shot Put** | Boys' Shot Put | Boys' Shot Put | SCORE_COLLISION_TIE |
| `13c3dc9bfd1ad43b` | Yes | How many years after being formed did the LA kings win the Stanley Cup ? | **47** | 47 | 47 | SCORE_COLLISION_TIE |
| `1f7e1ba710ad54f2` | Yes | For whom was this neighborhood constructed in the 18th century located in the district whose name means old city in Catalan ? | **the Ribera neighborhood** | the residents of the Ribera neighborhood | the residents of the Ribera neighbourhood | SCORE_COLLISION_TIE |
| `0f833e3694953c83` | Yes | What is the Date ( s ) & Architect for the armoury for which the Duke of York , as a member of the Canadian Royal Family , acts as Colonel-in-Chief ? | **1914-5 David Ewart** | 1905–1906; Thomas W. Fuller | 1914‑5 David Ewart | SCORE_COLLISION_TIE |
| `90a96e96bee8325f` | Yes | What type of aircraft does an Emmen Air Base-based squadron use that is an American business jet introduced in October , 1994 ? | **Cessna Citation Excel ( Model 560XL )** | Cessna Citation Excel | Cessna Citation Excel | SCORE_COLLISION_TIE |
| `f5de2c3184919462` | Yes | Which governor who 's seat is up in 2020 is not a commander-in-chief ? | **Roy Cooper** | John Carney | Roy Cooper | SCORE_COLLISION_TIE |
| `f0c414073dddf010` | Yes | What were the sales in millions of the song written and produced by The Smeezingtons ? | **10.2** | 10.2 | 10.2 | SCORE_COLLISION_TIE |
| `04dae7533cca3989` | Yes | What is the name of the company is located in the seventh-largest country by area and the second-most populous country ? | **Dhruva Space** | Dhruva Space | Dhruva Space | SCORE_COLLISION_TIE |
| `c1e3a043a66570cb` | Yes | Which group has ownership of the park that earned Best Landscaping in 2002 from Amusement Today ? | **SeaWorld Entertainment** | SeaWorld Entertainment | SeaWorld Entertainment | SCORE_COLLISION_TIE |
| `1e911a9dd9d2677f` | Yes | what country submitted a not nominated film that had a director who born 1944 ? | **Cuba** | Cuba | Cuba | SCORE_COLLISION_TIE |
| `7913b9d158c57cf6` | Yes | what is the sport of the silver medalist born 17 March 1973 ? | **Short track speed skating** | Speed skating | Speed skating | MULTIPLE_STRUCTURAL_CANDIDATES |
| `ccbdad20297be087` | Yes | The NAIA-affiliated Nebraska school is located how far ( in miles ) from the city of Lincoln ? | **50 miles** | 50 miles | 50 miles | SCORE_COLLISION_TIE |
| `9ee1522a253c8c51` | Yes | What is the nickname of the person from the class of 1951 ? | **Dr. Rendezvous** | Dr. Rendezvous | Dr. Rendezvous | SCORE_COLLISION_TIE |
| `743fa36d53b80a75` | Yes | Consider the titles in 1929 what is the title name where John Ford directed and starred George OBrien ? | **Salute** | Salute | Salute | SCORE_COLLISION_TIE |
| `40fda95a874e6fe5` | Yes | What is the name of the keyboardist in the band that formed in London in 2007 and had an album that spent 196 weeks in the UK album charts ? | **Isabella Summers** | Isabella Summers | Isabella Summers | SCORE_COLLISION_TIE |
| `f227f54a03795a22` | Yes | The driver who held the record for most Grand Prix victories until 2001 finished in what position ? | **7** | 7 | 7 | SCORE_COLLISION_TIE |
| `247f15347d58e54a` | Yes | For the owner who made the cover of TIME magazine on May 7 , 1934 , what was the horse name ? | **Busher** | Busher | Busher | SCORE_COLLISION_TIE |
| `65f7e37a42f61766` | Yes | For how many years did the politician associated with Dillard University serve in the House of Representatives ? | **4** | 4 | 4 years | SCORE_COLLISION_TIE |
| `aa1d42444bf86284` | Yes | What was the sequel to the film distributed by the distributor owned by The Walt Disney Company ? | **The Jewel of the Nile** | The Jewel of the Nile | The Jewel of the Nile | SCORE_COLLISION_TIE |
| `0828d6547108aeeb` | Yes | How many albums has this singer and song-writer sold , who won this award at the Staples Center in Los Angeles on September 13 , 2000 ? | **20 million albums** | 20 million | 20 million | SCORE_COLLISION_TIE |
| `8b5f97a47681ff1f` | Yes | What is the nickname of the club that Bob Cheek played for ? | **The Kangaroos** | The Roosters | The Roosters | SCORE_COLLISION_TIE |
| `1038a369bfdb7a65` | Yes | When did the season the winner club was the one established on 20 July 2013 commence ? | **9 January 2016** | 21 September 2013 | 21 September 2013 | SCORE_COLLISION_TIE |
| `984fa890db28c452` | Yes | Where is this rugby team based in that was the runners-up during the last season of the expanded Super 14 format ? | **Cape Town** | Christchurch, New Zealand | Cape Town | SCORE_COLLISION_TIE |
| `b4c59444af6231ab` | Yes | How many people in 2010 lived in the city that is home to Deerbrook Mall ? | **15,133** | 15,133 | 15,133 | MULTIPLE_STRUCTURAL_CANDIDATES |
| `4fbda71f56b9cb8e` | Yes | How many seasons has the team that last made the Finals in 2011 played ? | **36** | 8 | 8 | MULTIPLE_STRUCTURAL_CANDIDATES |
| `ad40926595d1d394` | Yes | What is the season year whose winner 's nickname is `` The Brazilians '' ? | **1998-99** | 1998-99 | 1998‑99, 1999‑00, 2000‑01, 2002‑03 | SCORE_COLLISION_TIE |
| `42542320beed1e31` | Yes | In what year did the person in fourth place die ? | **2004** | 2004 | 2004 | SCORE_COLLISION_TIE |
| `5b5c2e3cec81d1bf` | Yes | What product is produced in the place of the community when translated in Hawaiian means abruptly or sharp break ? | **Sugar** | sugar | sugar | SCORE_COLLISION_TIE |
| `dd013edf891ef6b1` | Yes | Where were the Olympics held whem Jocelyn Joseph was the flag bearer for Antigua and Barbuda ? | **Seoul** | Seoul, South Korea | Seoul | SCORE_COLLISION_TIE |
| `93ae174fd15b5315` | Yes | How many premierships in the AFL Women 's competition has the Club won who drafted a player who won the Brownlow Medal in 2008 ? | **one** | 1 | 1 | SCORE_COLLISION_TIE |
| `c21990dc1e6933b6` | Yes | Who composed the song performed by Al Jarreau ? | **Dave Brubeck** | Al Jarreau | Dave Brubeck | SCORE_COLLISION_TIE |
| `40ce4d51c0518488` | Yes | Where is the series which is currently running filmed ? | **Vancouver , British Columbia** | Vancouver, British Columbia | Vancouver, British Columbia | SCORE_COLLISION_TIE |
| `96071d9f3186a6d0` | Yes | What is the club whose previous MLS cup appearance was the inaugural season of Major League Soccer , and whose next MLS cup appearance was in 2010 ? | **Dallas Burn/FC Dallas** |  | Dallas Burn/FC Dallas | SCORE_COLLISION_TIE |
| `4f6047b8db1c80b1` | Yes | between the members born January 22 , 1880 and March 20 , 1916 what is the name of the university holding the chapter of the one born earlier ? | **University of Utah** | University of Utah | University of Utah | SCORE_COLLISION_TIE |
| `42c80d558887db58` | Yes | Of the places in the city that was listed as a town in the 2000 census , which was built for the director of Newberry Cotton Mills ? | **George Mower House** | George Mower House | George Mower House | SCORE_COLLISION_TIE |
| `e9188b67cb402773` | Yes | How many people inhabit the metro area of the city that María José González Ginestre is from ? | **1,827,165** | 6,661,949 | ≈2.5 million people. | SCORE_COLLISION_TIE |
| `336b0c6eabe3b0ee` | Yes | What is the name of a third listed museum located in a municipality in the Bernina region in the canton of Grisons ? | **Fondazione Ernesto Conrad** | Fondazione Ernesto Conrad | Fondazione Ernesto Conrad | SCORE_COLLISION_TIE |
| `330785d81c36c0ed` | Yes | What 's the village name of the Anglican denomination location that straddles A29 ? | **Ockley** | Ockley | Ockley | SCORE_COLLISION_TIE |
| `2b9da4e384687fd3` | Yes | What event did a country debut in who had an athlete medal at the 2005 Jeux de la Francophonie ? | **equestrian** | marathon | marathon | SCORE_COLLISION_TIE |
| `ab2f2db9e8eba2fe` | Yes | Who directed the film title with the cast member who met her demise on January 14 , 1957 ? | **Nicholas Ray** | Nicholas Ray | Nicholas Ray | SCORE_COLLISION_TIE |
| `e50c0fc0644c1817` | Yes | What is the English title of the film whose director was born on 11 October 1961 ? | **Omar** | Paradise Now | Paradise Now | SCORE_COLLISION_TIE |
| `ea69e6a660f77973` | Yes | Which road goes down the coast of the city that Project Runway contestant Ben Chmura resided in ? | **Bayshore Boulevard** | Bayshore Boulevard | Gulf Coast Highway | SCORE_COLLISION_TIE |
| `0ccec805fd3393f1` | Yes | Which author of the Kamakura period treasures died more recently ? | **Fujiwara no Teika** | Fujiwara no Teika | Fujiwara no Shunzei | SCORE_COLLISION_TIE |
| `6cb136a60e6330a5` | Yes | What was this SuperLiga season called when the team based in the second largest city in Serbia was the runners-up ? | **Jelen SuperLiga** | Jelen SuperLiga | Jelen SuperLiga | SCORE_COLLISION_TIE |
| `7d2cbbdbecead98c` | Yes | What was the person who founded the Shamrock Hotel known to be the king of ? | **Wildcatter** | the Wildcatters | the Wildcatters | SCORE_COLLISION_TIE |
| `610e3e5d00b5d538` | Yes | Who primarily wrote the lyrics for this Spanish pop band that won the Best Pop Album award at the 7th Annual Latin Grammy Awards ? | **Xabi San Martín** | Amaia Montero | Amaia Montero | SCORE_COLLISION_TIE |
| `daa6e17ad8c5c495` | Yes | What famous person was born at the site where the church is , in the city on the list with a population of 286 ? | **Jefferson Davis** | Jefferson Davis | Jefferson Davis | SCORE_COLLISION_TIE |
| `ad50ce5a5cfdf5d5` | Yes | Of the winners in 2005 and 2006 which one was born second ? | **Julius Kiptum Rop** | Julius Kiptum Rop | Julius Kiptum Rop | SCORE_COLLISION_TIE |
| `08205f09fb779e71` | Yes | What are the notes for the player that is now an assistant coach at North Melbourne , having previously been an assistant coach at the Carlton Football Club from 2013 to 2015 ? | **Retirement , effective end of season** | Retirement , effective end of season | Retirement, effective end of season | SCORE_COLLISION_TIE |
| `fda8b206d9074ed8` | Yes | What is the population as of 2017 of the location with 12 stands ? | **14,462** | 12,500,000 |  | SCORE_COLLISION_TIE |
| `6526d5135d5d0fa4` | Yes | What was the score when the runner up was a Romanian sports society , based in Bucharest ? | **5-2** | 5-2 | 5-2 | SCORE_COLLISION_TIE |
| `a1b0c95f119b18e9` | Yes | In which year was this historic Methodist church added to the National Register that was built about 1840-1850 in a city of 2,084 residents as of 2010 ? | **1840** | 1978 | 1978 | SCORE_COLLISION_TIE |
| `b96a6a7c2a76aec7` | Yes | Duchy of one of the constituent states of the German Confederation , the husband of what Grand Duchess of Russia gave up her Russian title to marry him ? | **Grand Duchess Elena Pavlovna of Russia** | Grand Duchess Elena Pavlovna of Russia | Grand Duchess Elena Pavlovna of Russia | SCORE_COLLISION_TIE |
| `165d33037a93a87e` | Yes | How many meters horizontally has the person who obtained 6741 points in heptathon in Talence leaped ? | **7.48** | 7.48 m | 7.48 m | SCORE_COLLISION_TIE |
| `32222ab2ecfc3a05` | Yes | To whom does Elemental ( software ) 's developer supply software ? | **Half of the world 's 20 largest drugmakers** | Dotmatics | Dotmatics | SCORE_COLLISION_TIE |
| `044096c45b19980e` | Yes | The college that opened in 1981 is located on how many acres of land ? | **47 acres** | 47 acres | 47 acres | SCORE_COLLISION_TIE |
| `1553992ce59467a8` | Yes | What town was a band formed who had a single that peaked at number 68 in Australia ? | **Geelong** | Geelong | Geelong | SCORE_COLLISION_TIE |
| `0587e5b090016e0b` | Yes | What is the population , as of the 2010 census , of the city where a site is also where the Eastern Prairie Fringed Orchid is found ? | **34,932** | 34,932 | 34,932 | SCORE_COLLISION_TIE |
| `e2ef1b958e7c8ef5` | Yes | What is the original chapter of the sister whose notability elected Tijjani Muhammad-Bande of Nigeria on June 4 , 2019 ? | **Honorary** | Honorary | Eta Beta Omega | MULTIPLE_STRUCTURAL_CANDIDATES |
| `61bcf886e23ad52c` | Yes | What is the name of the player that plays for the club that entered the AIHL in 2002 ? | **Austin McKenzie** | Jonathon Bremner | Jonathon Bremner | SCORE_COLLISION_TIE |
| `acfe4293fab8d45c` | Yes | How many national championships did the team that won the competition that is organised every year by EHF ? | **30 national championships** | 30 | 30 | SCORE_COLLISION_TIE |
| `d7a13239863ff8e8` | Yes | Which two kingdoms came from three kingdoms being joined together in the homeland of Ki-Seong Kim ? | **Silla and Balhae** | Silla and Balhae | Unified Silla and Goryeo | SCORE_COLLISION_TIE |
| `f7bbdf4a7ba0bd43` | Yes | What is the college of the person who was educated at Ruabon Grammar School ? | **Regent 's Park** | Regent 's Park | Regent's Park College, Oxford | SCORE_COLLISION_TIE |
| `0171bb0fbb6697b5` | Yes | In which year was this skier become an elected politician who won a medal at the Olympics Games that had 2,176 athletes from 72 nations ? | **2019** | 2019 | 2019 | SCORE_COLLISION_TIE |
| `0489f0ea296a2450` | Yes | What is the name of the area where the station with a UHF of 45- is located ? | **Crawley Court** | Preseli | Preseli | SCORE_COLLISION_TIE |
| `03b74593d042dc96` | Yes | In the village that was previously an isolated ranch that housed four families , what was the historic place also known as ? | **Chamblis Hotel** | Santa Clara | Chamblis Hotel | SCORE_COLLISION_TIE |
| `2bb97be294564fea` | Yes | What disease killed the person who played Maurice Lalonde in Highlander ? | **cancer** | cancer | cancer | SCORE_COLLISION_TIE |
| `e5537f254c94bdea` | Yes | What district is the city in Austria that hosted the Diplomacy Tournament located in ? | **Oberpullendorf** | Güssing | Oberpullendorf | SCORE_COLLISION_TIE |
| `3083024fbaf37edb` | Yes | Which languages have the works of the worst dancer of samba in Let 's Dance 2011 been translated into ? | **French , English , German , Norwegian and Finnish** | French, English, German, Norwegian, Finnish | French, English, German, Norwegian, Finnish | SCORE_COLLISION_TIE |
| `c1f49af7526d9ef2` | Yes | Who established the school that was the 2nd place winner of the 2002 Head of the River ( Queensland ) ? | **Society of the Sacred Heart** | Stuartholme | the Sisters of the Sacred Heart | SCORE_COLLISION_TIE |
| `8a0c9f5861500669` | Yes | What is the name of the club whose city/town is situated between Kgale and Oodi Hills ? | **Gaborone United** | Township Rollers | Prisons XI | SCORE_COLLISION_TIE |
| `74aea7a48604f353` | Yes | How many more goals did the player who debuted for Sweden , at age 17 , on 6 February 1996 have compared to Julie Fleeting ? | **1** | 1 | 1 | SCORE_COLLISION_TIE |
| `4950879950bb5189` | Yes | What year of the member of the Hong Kong films entered the music industry ? | **2007** | 1999 | 2007 | SCORE_COLLISION_TIE |
| `30634b9b79129a46` | Yes | In what season was the first Spanish professional basketball player on this list a rising star ? | **2006** | 2006-07 | 2006‑07 | SCORE_COLLISION_TIE |
| `1ca8ffcd3e20e498` | Yes | What is the historic place whose city or town is also a regional transportation center , located along U.S . Routes 20 and 65 and the Canadian National and Union Pacific Railroads ? | **Edgewood School of Domestic Arts** | Iowa Falls Union Depot | Iowa Falls Bridge | SCORE_COLLISION_TIE |
| `1dce3877f261dfbc` | Yes | Which PNP member was elected to the Senate first ? | **Itzamar Peña** | Itzamar Peña | Itzamar Peña | SCORE_COLLISION_TIE |
| `46f2d77f8de1586c` | Yes | How many new competitions were at the games where an athlete competed who was the gold medalist at 2017 Hochfilzen in 7.5 km sprint ? | **twelve** | 12 | 12 | SCORE_COLLISION_TIE |
| `857ba79b2fe601be` | Yes | What was the time of the runner that participated in the Olympics the most number of times ? | **1:10:57** | 1:10:39 | 1:10:39 | SCORE_COLLISION_TIE |
