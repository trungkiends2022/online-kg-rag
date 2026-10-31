# Benchmark Comparison: OUEG vs Direct LLM (N=200)

- **Total Evaluated Cases**: 200
- **Ambiguous Cases (Multiple structural ties/candidates)**: 141 (70.5%)
- **Unambiguous Cases**: 59 (29.5%)

## Overall Performance

| Metric | Direct LLM | OUEG (Online Unified Evidence Graph) | Delta (OUEG - Direct) |
|---|---|---|---|
| **Exact Match (EM)** | 56.50% | 60.00% | +3.50% |
| **Semantic EM** | 59.50% | 62.00% | +2.50% |
| **Token F1** | 68.11% | 73.20% | +5.09% |
| **Empty Answer Rate** | 1.50% | 1.00% | -0.50% |
| **Avg Latency (sec)** | 5.61s | 21.43s | +15.82s |

## Ambiguity Breakdown

| Subset | Count | Direct LLM EM | OUEG EM | Direct LLM F1 | OUEG F1 |
|---|---|---|---|---|---|
| **Unambiguous Cases** | 59 | 64.41% | 69.49% | 77.54% | 81.27% |
| **Ambiguous Cases** | 141 | 53.19% | 56.03% | 64.16% | 69.82% |

## Case Inspection: Ambiguous Samples

| ID | Ambiguous? | Question | Gold Answer | Direct LLM Answer | OUEG Answer | Status / Candidates |
|---|---|---|---|---|---|---|
| `c11b0740b1084da0` | Yes | In what country is the dome with a diameter just smaller than 15.80 located in ? | **northern** | Jordan | Italy | SCORE_COLLISION_TIE |
| `2e204d948cf1e89f` | Yes | Ref . [ 1 ] has a Municipality with a population of how many people ? | **25,062** | 14,025 | population not given | SCORE_COLLISION_TIE |
| `cba3193095a3662c` | Yes | The daughter of a former elected governor of PR , was the first woman to attempt to gain office in the state 's government , but lost to what member of the New Progressive Party ? | **Pedro Rosselló** | Luis Fortuño | Pedro Rosselló | SCORE_COLLISION_TIE |
| `09828a9a107af8a4` | Yes | Which championship occurred first ? Was it one which was originally raced in 1927 and won by Joe Davis , or the one which Judd Trump often wins ? | **German Open** | The first championship was held in 1927 and was won by Joe Davis. | World Snooker Championship | SCORE_COLLISION_TIE |
| `a622f85707546edf` | Yes | Of the athletes from the United States , who was born later ? | **Michael Weiss** | Michael Weiss | Michael Weiss | SCORE_COLLISION_TIE |
| `4dcf6e19c3bb39b5` | Yes | What is the origin of this language spoken in the archipelago off the west coast of mainland Scotland ? | **Old Irish** | It developed out of Old Irish. | It developed from Old Irish. | SCORE_COLLISION_TIE |
| `f3a72258757283ac` | Yes | Who is the owner of the location that is named after the British Queen consort ( and Electress of Hanover ) ? | **University of Virginia** | University of Virginia | University of Virginia | SCORE_COLLISION_TIE |
| `0f2bbfd98ea1504c` | Yes | How was eligibility ascertained for participation in the event that held first in the seventh month of 2009 ? | **determined on residence** | Eligibility to play in a national championship was determined on residence instead of nationality. | by residence | SCORE_COLLISION_TIE |
| `237f9bbf883540da` | Yes | What is the name of the route that goes via the location whose population was 9,449 at the 2010 census ? | **CR 202** | CR 201 | CR 208 | SCORE_COLLISION_TIE |
| `29f1edd261eba60a` | Yes | When the production was in 1997 , what Leslie Nielsen picture was the director known for ? | **2001 : A Space Travesty** | 2001 : A Space Travesty | 2001 : A Space Travesty | SCORE_COLLISION_TIE |
| `de9ea9da4ae38867` | Yes | Who beat the team in the World Series whose manager managed the Toronto Blue Jays from 1982 to 1985 ? | **Minnesota Twins** |  | Toronto Blue Jays | SCORE_COLLISION_TIE |
| `f90fc05e4102a348` | Yes | In what year was the team who played at Woodlands Stadium inducted into the S.League ? | **1996** | 1996 | 1996 | SCORE_COLLISION_TIE |
| `0efa450ba026b39a` | Yes | What is the nationality of the women 's winner of the Zevenheuvelenloop who competed in 2019 in a rarely held race that is not recognized as an Olympic event ? | **Ethiopian** | Ethiopian | Ethiopian | SCORE_COLLISION_TIE |
| `4c40367a6ffb101b` | Yes | Which team had more total ? Is it the team who takes a lot of pride in their success in qualifying for the Rugby World Cup for their first and so far only time in 1995 , or the team classified as a tier two rugby nation who play in red and white ? | **Canada** | Canada | Canada | SCORE_COLLISION_TIE |
| `b4d318580064d596` | Yes | What effect on the organ does the pathophysiology have that is associated with a preventable cause of intellectual disability ? | **gross enlargement** | Hyperplasia of the thyroid | hyperplasia of the thyroid | SCORE_COLLISION_TIE |
| `ef789b3bd4bae41e` | Yes | What volleyball athlete was born in 1959 ? | **Eiji Shimomura** | Eiji Shimomura | Eiji Shimomura | SCORE_COLLISION_TIE |
| `942c391ecf3f6acd` | Yes | What are the total caps of the player whose team won the now-defunct Copa Interamericana in 1998 ? | **1 ( 120 )** | 120 | 1 ( 120 ) | SCORE_COLLISION_TIE |
| `ca7e39005fb5e7e5` | Yes | What is the ending point of the route whose starting point is in a city that was converted to parkland under the terms of the Metropolitan Commons Act 1878 ? | **Crystal Palace** | Crystal Palace | Crystal Palace | SCORE_COLLISION_TIE |
| `5270a688518635c4` | Yes | What is the language family for the language that was spoken in the Finke River area , near the Overland Telegraph Line station at Charlotte Waters ? | **Pama-Nyungan** | Arandic | Pama‑Nyungan | SCORE_COLLISION_TIE |
| `350fca3fe81d23e7` | Yes | Which location is linked to the New Testament church father who is considered the pre-eminent Latin writer of Western Christianity until Jerome and Augustine ? | **Carthage** | Carthage | Carthage | SCORE_COLLISION_TIE |
| `ffd446eb1b40e694` | Yes | What is the league whose city has a history of over 2,200 years and was a major terminus of the maritime Silk Road ? | **Hong Kong Premier League** | Chinese Super League | Chinese Super League | SCORE_COLLISION_TIE |
| `2690c08b9f7d8ba8` | Yes | What is the full name of the guest from November 3 ? | **James Todd Spader** | James Spader | James Spader | SCORE_COLLISION_TIE |
| `49a05ba340d7f0b7` | Yes | Who was the commander of the Scots in the 1138 battle at Yorkshire , England ? | **David I** | King David I of Scotland | King David I of Scotland | SCORE_COLLISION_TIE |
| `6a6fed001116d24f` | Yes | The flag bearer at the Rio and London Games competed in what event ? | **400m** | 400m | 400 m | SCORE_COLLISION_TIE |
| `7d56ec784668c180` | Yes | Who directed the film portraying the events of the Wannsee Conference ? | **Heinz Schirk** | Heinz Schirk | Heinz Schirk | SCORE_COLLISION_TIE |
| `08466917653bd712` | Yes | When was the organization with two titles founded ? | **1927** | 1927 | 1927 | SCORE_COLLISION_TIE |
| `454175cc4a477252` | Yes | What is the date of the station whose river is Eastern Canada 's longest river ? | **1931** | 1962 | 1962 | SCORE_COLLISION_TIE |
| `2375c1c21c7cd32d` | Yes | What was corrected in the Olympic Games in which Rajendra Bahadur Bhandari bore the flag for Nepal ? | **medal obverse** | the stripping of medals from three athletes after they were found to have used banned substances | the final medalists were corrected. | SCORE_COLLISION_TIE |
| `32f2e953e386d39d` | Yes | How many women governors have held the governor position of the politician who became an attorney with Latham & Watkins ? | **Four** | 0 | 0 | SCORE_COLLISION_TIE |
| `c281f92a7917f0b8` | Yes | How many people live in the home city of the club that finished in 2nd place overall in 2011 ? | **2.9 million** | 2.9 million | 2.9 million people | SCORE_COLLISION_TIE |
| `0fb72fb371fb412a` | Yes | Whose violation was the first one to occur in the 21st century ? | **Tony Dees** | Tony Dees | Vadim Devyatovskiy | SCORE_COLLISION_TIE |
| `46a33c66deb0e662` | Yes | What category/ recipient won the award for feature length films shown at major international film festivals ? | **Stalker** | for Stalker | Stalker | SCORE_COLLISION_TIE |
| `073ce2c527261e10` | Yes | The Austrian skier born in Radstadt in 1975 won the Silver medal in the event that the Gold medal winner was from what country ? | **France** | France | Austria | SCORE_COLLISION_TIE |
| `996ff24a70994a65` | Yes | What is the alumni base of the university located in North Carolina that was chartered in 1932 ? | **55,000** | around 55,000 | around 55,000 | SCORE_COLLISION_TIE |
| `a48d1f9328764501` | Yes | What is the company name whose headquarters city identifies with the medieval trading port of Julfar ? | **Commercial Bank International** | Commercial Bank International | Commercial Bank International | SCORE_COLLISION_TIE |
| `f6698886d0eb7ddc` | Yes | For which country did the gymnast that received four world championships medals ( one silver and three gold ) andfour European championships medals ( two gold and two bronze ) compete ? | **Romania** | Romania | Romania | SCORE_COLLISION_TIE |
| `a9ee53ddb1011c5b` | Yes | What is the biggest city in the state that is home to Standing Rock Indian Reservation ? | **Sioux Falls** | Fort Yates | Fargo | SCORE_COLLISION_TIE |
| `17e98a1f02b64f21` | Yes | The senator who was also President of the Belgian Senate was appointed by which parliament ? | **Walloon** | the Flemish Parliament | Walloon Parliament | SCORE_COLLISION_TIE |
| `0885f9744bf8f219` | Yes | Which of the churches in the town that was built by George Andrew is the oldest ? | **St Paul 's Parish Church** | St Paul's Parish Church | St Paul’s Parish Church | SCORE_COLLISION_TIE |
| `0becf9cd7acf9c8a` | Yes | What material is the landmark made of that is on Main Street and in the city named by early Spanish navigators in honor of the Viceroy of New Spain ? | **coast redwood** | coast redwood | coast redwood | SCORE_COLLISION_TIE |
| `801ae6f8c0fe1f4c` | Yes | What medal did the flag bearer win at the Olympic Games in which eleven people were killed by Black September terrorists ? | **gold medal** | gold | gold | SCORE_COLLISION_TIE |
| `695afc0a3320cccc` | Yes | When did the most recently launched ship hit a reef and catch fire ? | **8 January 1971** | January 8 , 1971 | January 8 , 1971 | SCORE_COLLISION_TIE |
| `a548cf7f4091c546` | Yes | What was the literal English translation of the name of the currency used until 2009 in the country where the capital and largest city is Bratislava ? | **Slovak crown** | Slovak crown | Slovak crown | SCORE_COLLISION_TIE |
| `9f6ae8eaab015b27` | Yes | Besides the director , who co-wrote the 2012 film from the United Kingdom ? | **Rae Brunton** | Jonathan Nolan | Rae Brunton | MULTIPLE_STRUCTURAL_CANDIDATES |
| `a6bd2e37d4c31372` | Yes | Who were runners up in the year when the most supported and most successful club in the league to date were first champions ? | **Adelaide United** | Adelaide United | Adelaide United Football Club | SCORE_COLLISION_TIE |
| `38c022dc75b42938` | Yes | Of the teams that did not play in the top division last season , the oldest one plays out of a stadium that was originally built to host what event ? | **1999 Summer Universiade in Palma** |  |  | SCORE_COLLISION_TIE |
| `1fa003313e977227` | Yes | What is the average depth , in feet , of the feature also known as the Central Polar Basin ? | **12,960** | 12,960 ft | 12,960 ft | MULTIPLE_STRUCTURAL_CANDIDATES |
| `05fafefcf4185b3f` | Yes | What is the nickname of the gold medalist who competed in the Men 's Slalom B event ? | **Macca** | Bob | Bob | SCORE_COLLISION_TIE |
| `7a2b46741c809315` | Yes | Which team did the driver that finished fastest in the qualifying round of the 2005 British Grand Prix make his Formula One debut with ? | **Minardi** | Sauber‑Petronas | Minardi | SCORE_COLLISION_TIE |
| `99de0bbd50952a70` | Yes | The extinct language also called Canaanite is part of a language family that is itself a branch of what language family ? | **Afroasiatic** | Afroasiatic | Afroasiatic | SCORE_COLLISION_TIE |
| `04066ae60c7e6eb7` | Yes | What city is the at the end of an E-Road whose route is a city built on seven hills ? | **Ostrov** | Ostrov | Ostrov | SCORE_COLLISION_TIE |
| `da22c1c6e2e30c02` | Yes | What geographic feature does the Chilean city containing the stadium that can hold 18,750 lie in ? | **valley** | the Pacific Ocean | the Pacific coast | SCORE_COLLISION_TIE |
| `19f9db0257d6ab7c` | Yes | Which song in the Coast to Coast Album was also released acoustically ? | **No Place That Far** | Uptown Girl | Against All Odds | SCORE_COLLISION_TIE |
| `ef1dde11fb06ae2c` | Yes | In which state lays the burial place of the United States president that led the Union Army as Commanding General of the United States Army in winning the American Civil War ? | **New York City** | New York | New York | SCORE_COLLISION_TIE |
| `4b5be57c56bf35f5` | Yes | Who did the Jewish-American actor born in 2002 play on Andi Mack ? | **Jonah Beck** | Jonah Beck | Jonah Beck | SCORE_COLLISION_TIE |
| `4190e99b1fc0cd9c` | Yes | Which year did the person who completed the qualifying race of the Canadian Grand Prix of 1999 in 1:19.440 first get onto the podium ? | **1995** | 1999 | 1994 | SCORE_COLLISION_TIE |
| `9bef129a6736b09a` | Yes | Who was the director of the film cowritten by Paul Brickman ? | **Jon Avnet** | Jon Avnet | Jon Avnet | SCORE_COLLISION_TIE |
| `f21699a6e863e259` | Yes | What is the condition of the place that is the birthplace of the famous astronomer Tycho Brahe ? | **Private residence** | Private residence | Private residence | SCORE_COLLISION_TIE |
| `8f91418d35d553a1` | Yes | What school did the namesake of the place in Barnum attend ? | **University of Wyoming** | Northampton Academy | University of Wyoming | SCORE_COLLISION_TIE |
| `734e8bea79464be2` | Yes | Between 1959 and 1964 how many official world records did this athlete , who competed in the most populous city in California , set ? | **six** | 6 | six | SCORE_COLLISION_TIE |
| `2c9d29d60efd9722` | Yes | what is the age the player born 28 October 1973 ? | **46** | 46 | 52 | SCORE_COLLISION_TIE |
| `846fc6ee43ca7f7d` | Yes | What nationality was the athlete with the shortest throw ? | **Swedish** | SWE | Swedish | SCORE_COLLISION_TIE |
| `de75dc732fabe59e` | Yes | How many live in the country with fewer than 7 but more than 4 Wimbledon men 's singles title ? | **seven million** | 5 | approximately seven million | MULTIPLE_STRUCTURAL_CANDIDATES |
| `5d3e006c41a960d0` | Yes | Which town had a higher population ? One containing a historic aqueduct , or one containing a 2-story farm and barn built in 1883 ? | **Springfield Township** | Metamora | Metamora | SCORE_COLLISION_TIE |
| `4958ccdd051a2980` | Yes | Four years after a cartoon that was produced by Leon Schlesinger , there was a cartoon whose star appeared in how many cartoons ? | **46** | 46 | 46 | SCORE_COLLISION_TIE |
| `e170fbdcf6d8f02f` | Yes | The country that put out the most variations of an aircraft were all designed by this company ? | **Waco Aircraft Company** | Waco Aircraft Company | Waco Aircraft Company | SCORE_COLLISION_TIE |
| `aa5556d1a1aa881b` | Yes | When did the team with the second most games played change the spelling of their name ? | **1986** | 1986 | 1986 | SCORE_COLLISION_TIE |
| `dc2a5a4316ee78f5` | Yes | Which club did the oldest player that left club in 2011 , move to ? | **León de Huánuco** | Querétaro | Atlético Nacional | SCORE_COLLISION_TIE |
| `b99fc5c636ea823c` | Yes | In which year did the youngest son born to Archduke Franz Karl of Austria and Princess Sophie of Bavaria receive his honour ? | **1903** | 1903 | 1903 | SCORE_COLLISION_TIE |
| `e7b0cbf661de5786` | Yes | What church is the town with a club that won the Meath Senior Football Championship once in 1943 ? | **St Cianáns** | Duleek | St Cianáns Church | SCORE_COLLISION_TIE |
| `eceee4636954c5d4` | Yes | Who started the company that developed the game Magus ? | **Richie Casper** | Richie Casper | Richie Casper | SCORE_COLLISION_TIE |
| `dd410a79fd8c010a` | Yes | Who is the Pokémon Ranger in the video-game based movie released on July 15 , 2006 ? | **Jack Walker** | Jack Walker | Jack Walker | SCORE_COLLISION_TIE |
| `b7a4e18bef82b6a6` | Yes | What is the capacity of the stadium whose team chose to play in the 2012 Copa Perú ? | **24,000** | 24,000 | 24,000 | SCORE_COLLISION_TIE |
| `75e2191eee16f8ef` | Yes | For what is this South African football striker renowned for whose team was sponsored by this multinational corporation , founded in Herzogenaurach , Germany ? | **trickery and explosive pace** | his trickery and explosive pace | trickery and explosive pace | SCORE_COLLISION_TIE |
| `74c78bc9ffb4fd39` | Yes | What is the birthday of Ford 's oldest winning driver ? | **October 28 , 1944** |  | June 23 1948 | SCORE_COLLISION_TIE |
| `df3960a33dba9f33` | Yes | Which city did the 2018 film in which Aiden Turner played Young Calvin Barr debut at ? | **Montreal** | Montreal | Montreal | SCORE_COLLISION_TIE |
| `755c521b5d638fd0` | Yes | In which place did the team that holds its matches on the stadium that hosted the Norwegian Athletics Championships in 1968 ended up in the last norwegian first division season ? | **8th** | 8th | 8th | SCORE_COLLISION_TIE |
| `677d98894290e638` | Yes | What was the first honour for the person who was Emir of Afghanistan from 1901 until 1919 ? | **GCMG** | GCMG | GCMG | SCORE_COLLISION_TIE |
| `e21b2fa14b6b032b` | Yes | What type of grapes are used to make the champagne of the champagne house founded in 1849 in a town known for coronations of french royalty ? | **Grand Cru** | Grand Cru grapes | Grand Cru grapes | SCORE_COLLISION_TIE |
| `02b6448b566066f0` | Yes | What was the year of completion for the church that is a Grade II listed building ? | **1860** | 1861 | 1861 | SCORE_COLLISION_TIE |
| `5e0799c6fdd412fd` | Yes | The player born in Nacogdoches , Texas in 1983 was selected to the 2005 All-Star game while playing for a team whose owner also owns what NFL team ? | **New England Patriots** | New England Patriots | New England Patriots | SCORE_COLLISION_TIE |
| `8981c9f66cddf3a2` | Yes | What club does the athlete currently coach who won a silver medal in what was also called `` Ice Dance '' ? | **TUS Stuttgart** | TUS Stuttgart | TUS Stuttgart | MULTIPLE_STRUCTURAL_CANDIDATES |
| `f0705ce2a96650c1` | Yes | How many people live in the city where the most recent event took place ? | **240,342** | 240,342 | 240,342 | SCORE_COLLISION_TIE |
| `d2d47943e912524b` | Yes | Who was the director of the title that had a particular focus on the necessity of liberalising divorce laws ? | **Frank Hauser** | Frank Hauser | Frank Hauser | SCORE_COLLISION_TIE |
| `d82506405d5a9184` | Yes | The school whose trustees are the Worshipful Company of Brewers is served by a bus route that starts in which district ? | **East Finchley** | Finchley | Finchley | SCORE_COLLISION_TIE |
| `8bee2d1e7e68a51a` | Yes | What are the considered weaknesses of the player recruited by the club that has won thirteen VFL/AFL premierships ? | **slight frame , weighing just 70 kilograms** | His weaknesses were considered to be his slight frame, weighing just 70 kilograms. | a slight frame, weighing just 70 kg | MULTIPLE_STRUCTURAL_CANDIDATES |
| `2a9b60a7d68a2c15` | Yes | A member of the South Carolina House of Representatives was part of a chapter that was formed after what conflict ? | **American Civil War** | World War I | World War II | SCORE_COLLISION_TIE |
| `89e1c7f63ef47776` | Yes | What is the length in km of the county route that cross the eastern part of the american state of New York ? | **2.11** | 2.11 | 3.36 km | SCORE_COLLISION_TIE |
| `15104ba3ef52de9c` | Yes | What county has extended parts of the city which contains Morris Brown College ? | **DeKalb** | Lexington County | DeKalb County | SCORE_COLLISION_TIE |
| `c3e1e6d2d4aafc2d` | Yes | How did the musician with the single Keep Me a Secret put out his first album ? | **independently** | He independently released his debut album, “Growing flowers by candlelight.” | independently released | SCORE_COLLISION_TIE |
| `83a5e8e2d0754c27` | Yes | The club that achieved its first Grand Final appearance in 1990 signed a Second Row player in November of 2010 who is the younger brother of what player ? | **Rob Worrincy** | Rob Worrincy | Rob Worrincy | SCORE_COLLISION_TIE |
| `081ffd9675ed0a78` | Yes | What was the release date of the game that is often referred to as an RPG ? | **August 1 , 2013** | August 1, 2013 | August 1 , 2013 | SCORE_COLLISION_TIE |
| `286fc3b35ad650ae` | Yes | What is the shape of the bacterium source of the restriction enzyme Sau3AI ? | **round-shaped** | coccus | coccus (spherical) | MULTIPLE_STRUCTURAL_CANDIDATES |
| `38e3df079a67f984` | Yes | The Fuller Crater 's name was approved how many years after its namesake died ? | **30** | 30 | 30 | SCORE_COLLISION_TIE |
| `a51872818dcfbe82` | Yes | Who was the youngest member of the gold medal winning curling team ? | **Romano Meier** | Elena Stern | Romano Meier | MULTIPLE_STRUCTURAL_CANDIDATES |
| `4b12f17766fafc1d` | Yes | What is the national title of the film whose production country is a unitary parliamentary democracy and constitutional monarchy ? | **Dogville** | Dogville | Dogville | SCORE_COLLISION_TIE |
| `31fe5d56fd5bd58b` | Yes | What kind of dam is the tallest dam in Europe ? | **Gravity** | concrete gravity | Concrete gravity dam | SCORE_COLLISION_TIE |
| `145825860ef076ea` | Yes | Who is the director of the most recent film to feature one of Shende 's songs ? | **Gautham** | Ravi Jadhav | Gautham Menon | SCORE_COLLISION_TIE |
| `ce92d8c4b95ea926` | Yes | In 2010 , Sam Pinto played Elizaria in a series directed by whom ? | **Mark A. Reyes** | Don Michael Perez | Roxanne Picard | SCORE_COLLISION_TIE |
| `0daf43a0e7e64277` | Yes | What is the market capitalization of that has the fifth largest revenue of publicly traded companies in Japan ? | **274,905** | 274,905 | 274,905 | SCORE_COLLISION_TIE |
| `b1b64b9b9b507e17` | Yes | What is the cause of death for the dancer who scored 20 on the Waltz ? | **Heart failure** | heart failure | heart failure | SCORE_COLLISION_TIE |
| `04e5db54d9ed2577` | Yes | At which air force base did the pilot who graduated in 1968 serve ? | **Hickam** | Andrews Air Force Base |  | SCORE_COLLISION_TIE |
| `b1eb73bc03b88f1a` | Yes | When was one of Wingina 's historic places destroyed in a fire ? | **1955** | 1955 | 1955 | SCORE_COLLISION_TIE |
| `4aa27b1524aec682` | Yes | How many games ahead of the MLB team that doubled 356 times in 1930 did the Philadelphia Athletics end up that year ? | **21** | 21 | 21 | SCORE_COLLISION_TIE |
| `736e042b2c205104` | Yes | In 1379 , who founded the college that provided the education of the British oriental scholar who became a Boden Professor of Sanskrit in 1937 and remained in the position until his death ? | **William of Wykeham** | William of Wykeham | William of Wykeham | SCORE_COLLISION_TIE |
| `8304a837abe2e7cf` | Yes | When did the cathedral located in Cornwall open ? | **1858** | 1858 | 1858 | SCORE_COLLISION_TIE |
| `0f22c2630c526d85` | Yes | What is the year of birth of the player who has scored 336 goals in 850 games in his career ? | **1978** | 1978 | 1978 | SCORE_COLLISION_TIE |
| `1902fd1fb4ac2542` | Yes | What position does this footballer play who used to play for this club Shenyang , Liaoning Province ? | **left winger** | left winger | left winger | SCORE_COLLISION_TIE |
| `dcc7a5f3ca9176ff` | Yes | For what year did Tanwar win an award at the show co-hosted by Manish Paul & Roshni Chopra in May in Mumbai ? | **2012** | 2012 | 2012 | SCORE_COLLISION_TIE |
| `9e54b91d0b09d23c` | Yes | Which year was the team in the higher league of Latvia that obtained a championship 15 times relegated to a lesser league ? | **2016** | 2016 | 2016 | SCORE_COLLISION_TIE |
| `337e706c344f4243` | Yes | What is the Identification/Remains of the watermill that drains an area of approximately 42 km2 ? | **Entire establishment** | Entire establishment | Entire establishment | SCORE_COLLISION_TIE |
| `51994b0c74870590` | Yes | What is the rank of the 555 meter South Korean building in the world in terms of height ? | **5th** | 5th | 1 | SCORE_COLLISION_TIE |
| `719ed89f043d9b8f` | Yes | When did the politician beaten by the current Minister of Mines and Energy resign as president of his party ? | **2016** | 2016 | 2016 | SCORE_COLLISION_TIE |
| `caeef3d21bc6029c` | Yes | Which people occupied the home country of Thomas Voeckler following the Gauls ? | **Rome** | Rome annexed the area in 51 BC, holding it until the arrival of Germanic Franks in 476 | the Romans and the Germanic Franks | SCORE_COLLISION_TIE |
| `f395e427c08989da` | Yes | In what league does the recruited from team currently play for that had a player who won a mail medal at the Encounter Bay Football Club in 2004 ? | **Tasmanian State League** | Tasmanian Football League | Tasmanian State League | SCORE_COLLISION_TIE |
| `0793f27829274525` | Yes | How many annual visitors are pulled in by the marathon that Tegla Loroupe won in 2002 ? | **2,500** | 2,500 | 2,500 tourists each year | SCORE_COLLISION_TIE |
| `61ddbed34b0d48d1` | Yes | In 2010 , how many people lived in the town where the Hagen Site is located ? | **4,935** | 4,935 | 4,935 | SCORE_COLLISION_TIE |
| `92801adfcf4a0a71` | Yes | What was the nickname of the second oldest patrol squadron ? | **Mad Foxes** | Mad Foxes | Mad Foxes | SCORE_COLLISION_TIE |
| `68299ddc88e29418` | Yes | What rank is the film written by Robert Ben Garant and Thomas Lennon ? | **6** | 6 | 6 | SCORE_COLLISION_TIE |
| `d9f05734005e6184` | Yes | What year was first mention of a city where a plane was shot down by the world 's first mass-produced supersonic aircraft ? | **742** | 1950 | 1964 | SCORE_COLLISION_TIE |
| `a79b7e51b2d6c017` | Yes | What is the name of the airport that lies on the outskirts of town where an attack occurred by a perpetrator that officially declared its support for National Bolshevism ? | **Ben Gurion Airport** | Ben Gurion Airport | Ben Gurion Airport | SCORE_COLLISION_TIE |
| `43248e2e2ae7edc0` | Yes | What year was the author born whose National Treasure is located in the Prefecture on the east coast of Honshu and largely consists of the Bōsō Peninsula ? | **1222** | 774 | 1222 | SCORE_COLLISION_TIE |
| `a98b74225985bd58` | Yes | About how many miles long is the coast of the country of birth of a recipient whose rank required hard physical labor , such as shoveling fuel ? | **12** | 12 miles | 12 miles | SCORE_COLLISION_TIE |
| `6d1600cf665e4b2b` | Yes | What was the title of the memoir of the author of Miss Suzy ? | **Mother Wore Tights** | Mother Wore Tights | Mother Wore Tights | SCORE_COLLISION_TIE |
| `248995baa9d16235` | Yes | What is the song title of the artist who is known for his participation in the Eurovision Song Contests of 1967 and 1969 ? | **Ik heb zorgen** | Ik heb zorgen | Ik heb zorgen | SCORE_COLLISION_TIE |
| `e9f351a7b62a265d` | Yes | Which prehistoric immigrants got to the continent of the nation with 500,000 residents with origins in Lebanon ? | **Paleo-Indians** | Levantine immigrants | Lebanese American | SCORE_COLLISION_TIE |
| `676633625f054d31` | Yes | What is the LGA for the School that was founded in 1990 and named in honour of Matthew Flinders ? | **Sunshine Coast** | Sunshine Coast | Sunshine Coast | MULTIPLE_STRUCTURAL_CANDIDATES |
| `99cc36248aa4887d` | Yes | What is the net worth of the Governor of the state that was admitted to the Union on June 20 , 1863 ? | **$ 1.59 billion** | $ 1.59 billion | $1.59 billion | SCORE_COLLISION_TIE |
| `8a2800728ad52f0b` | Yes | Considering the city located in the canton at the centre of Switzerland , what is its population size ? | **82,418** | 82,418 | 82,418 | SCORE_COLLISION_TIE |
| `88006e59b224e527` | Yes | The ranking member of the Human Services , Mental Health & Housing committee is a native of which state ? | **Alaska** | Alaska | Alaska | SCORE_COLLISION_TIE |
| `d5bac76eb5f684df` | Yes | What is the main devotion of this temple located in this city considered the cultural capital of Japan ? | **Yakushi** | Yakushi | Yakushi | SCORE_COLLISION_TIE |
| `65b69d46bd5b9ab4` | Yes | What temperature scale was invented in the city that was the capital of Sweden from 1273 to 1436 ? | **Celsius** | Celsius scale | Celsius scale | SCORE_COLLISION_TIE |
| `c770835b21a5efdf` | Yes | In what year was Dick Van Dyke presented with an award from BAFTA ? | **2017** | 2017 | 2017 | SCORE_COLLISION_TIE |
| `2ed4eb069159d494` | Yes | Which player transferred from the team that has won the domestic league 30 times ? | **Jaime Penedo** | Jaime Penedo | Jaime Penedo | MULTIPLE_STRUCTURAL_CANDIDATES |
| `b0ff46f166ab7d4e` | Yes | What actor who has appeared in over 100 films and TV shows , also stars in a sports film directed by Mars Callahan ? | **Christopher Walken** | Christopher Walken | Christopher Walken | SCORE_COLLISION_TIE |
| `0f7ce6861dae1933` | Yes | Which club did the all-time highest goalscorer of the Malaysia Super League move from ? | **Kelantan** | Kelantan | Kelantan | SCORE_COLLISION_TIE |
| `adcacf21eb6e93c2` | Yes | How many writers worked on the most recently released cartoon ? | **two** | 2 | 2 | SCORE_COLLISION_TIE |
| `9c3dc7011fdbf7ce` | Yes | When was the vessel in the class that consisted of 151 frigates launched ? | **14 December 1944** | 1945 | 1945 | SCORE_COLLISION_TIE |
| `8778337b7c71962f` | Yes | During the peak year of arcade and console games , what is the name of the main programmer that was involved in the game that as Lunar battle as working battle ? | **Rich Adam** | Rich Adam | Rich Adam | SCORE_COLLISION_TIE |
| `d67b931721866e23` | Yes | What services does the station have that is located between Avenue of the Americas and Seventh Avenue ? | **1 , 2 , 3** | L, F, M | F, M, 1, 2, 3 | SCORE_COLLISION_TIE |
| `3bebafaef21a679b` | Yes | How many federated states comprise the country that is the homeland of the artists who recorded the song with the word `` Stern '' in its title that was certified gold in Switzerland ? | **Nine federated states** | 9 | nine | SCORE_COLLISION_TIE |
