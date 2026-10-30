# Official live-results feeds, states AL to MO (25 states)

Probed 2026-10-30 from Juan's Mac (egress IP in Argentina, Chrome-style User-Agent, a handful of requests per state, no hammering). Samples are in `research/samples/<ST>/`.

Definitions
- **yes** = structured feed (JSON/CSV/TSV) that I fetched and parsed.
- **partial** = official source exists but it is HTML-only, or the structured feed exists and is blocked or unconfirmed from here.
- **no** = I could not reach any machine-readable data (blocked, PDFs only, or nothing found).
- **verified = yes** only if I fetched real data from the endpoint. "Live-configured" means the Nov 3 2026 election already exists on the endpoint with zero votes.

IMPORTANT access finding: many hosts block this machine, not the platform in general. Blocks seen (recorded only, none bypassed): AWS WAF JS challenge on Clarity data files (CO, IA), AWS WAF CAPTCHA on all of elections.alaska.gov, Cloudflare challenge (AZ, FL Election Watch), Cloudflare country/IP bans (KS error 1009, MO error 1005), CloudFront country block (ME), Akamai denial (KY "bot activity from your IP", MI), Radware CAPTCHA (MN), nginx 403 on Clarity AR/KY/AZ paths. Several of these are likely geo or IP rules and may behave differently from a US-based server. mapthemidterms.com (checked 2026-10-18) says it reads CA, CO, FL, GA, IA, MN, NE, NC, SD, TX, UT, WA files server-side, which suggests CO, IA, MN are readable from a US host. Juan should decide where the fetcher runs; I did not try to get around any block.

## Summary table

| State | Platform | Machine-readable | Endpoint pattern | County | District (US House) | Vote type | Verified |
|---|---|---|---|---|---|---|---|
| AL | Custom ASP.NET (www2.alabamavotes.gov/electionNight) | partial (HTML) | `/electionNight/statewideResultsByContest.aspx`, `/countyResultsByContest.aspx` | yes (HTML) | likely | unknown | no (pages up, no data) |
| AK | Custom, behind AWS WAF CAPTCHA | no | `elections.alaska.gov/results/<yy>GENR/` (blocked) | n/a | n/a | n/a | no |
| AZ | results.arizona.vote, behind Cloudflare challenge | no | blocked | n/a | n/a | n/a | no |
| AR | Clarity ENR (`/AR/`), 403 from here | no | `results.enr.clarityelections.com/AR/` (403) | n/a | n/a | n/a | no |
| CA | SOS JSON API (api.sos.ca.gov) | yes | `api.sos.ca.gov/returns/{governor\|us-rep/district/N\|<office>/county/<county>}` | yes | yes | no | yes (live-configured, zeros) |
| CO | Clarity ENR | partial (data files WAF-challenged) | `results.enr.clarityelections.com/CO/elections.json` OK; `/CO/<EID>/current_ver.txt` challenged | yes (statewide sums + county sites) | yes | yes (Clarity detail) | partial (elections.json only) |
| CT | CTEMS public portal (Angular + static JSON) | yes | `ctemspublic.pcctg.net/ng-app/data/election/108/<Version>/*.json` | town | via Lookupdata | ABR/EBR/EDR turnout counts | yes (live-configured) |
| DE | Static HTML on elections.delaware.gov | partial (HTML) | `elections.delaware.gov/results/enr/GE2026.html` (guess from `PR2026.html`) | yes | at-large | EV vs ED lumped | yes for 2026 primary page; GE page not up |
| FL | results.elections.myflorida.com (+ floridaelectionwatch.gov) | yes | POST `ResultsExtract.Asp` (TSV) | yes | yes (Juris1num) | no | yes (2024 gen and 2026 primary) |
| GA | Enhanced Voting | yes | `results.sos.ga.gov/results/public/api/elections/Georgia/<id>[/ballot-items]` | yes | yes | yes (4 types) | yes (2024); 2026 gen not yet listed |
| HI | Static TSV, elections.hawaii.gov | yes | `elections.hawaii.gov/wp-content/results/<Election>/media.txt` | precinct | yes | Mail vs In-Person | yes (2026 primary) |
| ID | Enhanced Voting | yes | `results.voteidaho.gov/results/public/api/elections/id/nov2026[/ballot-items]` | yes | yes | yes | yes (live-configured) |
| IL | ISBE CSV downloads | yes | `elections.il.gov/Downloads/ElectionOperations/ElectionResults/ByOffice/<elecId>/<elecId>-<contestId>-<NAME>-<yyyy>GE.csv` | precinct | yes | no | yes (2024 gen, 2026 primary) |
| IN | Custom ENR (Azure, static JSON) | yes | `enr.indianavoters.in.gov/site/data/settings.json` then `OffCatC_<cat>_<VersionType>.json` | yes | yes | in turnout file | yes (live-configured) |
| IA | Clarity ENR | partial (data files WAF-challenged) | `electionresults.iowa.gov/IA/elections.json` OK | yes | yes | yes | partial |
| KS | ent.sos.ks.gov (static HTML per county) | no from here | `ent.sos.ks.gov/kssos_ent.html` (Cloudflare 1009) | yes (105 pages) | probably | no | no |
| KY | SBE live results, Akamai-protected | no | `vrsws.sos.ky.gov/liveresults/` (blocked) | n/a | n/a | n/a | no |
| LA | voterportal.sos.la.gov (static JSON "htm") | yes | `voterportal.sos.la.gov/ElectionResults/ElectionResults/Data?blob=<yyyyMMdd>/Votes_Multiparish.htm` | yes (ByParish csv) | yes | early voting file | yes (live-configured) |
| ME | maine.gov/sos, CloudFront country block | no | blocked | n/a | n/a | n/a | no |
| MD | Static HTML, elections.maryland.gov | partial (HTML) | `/elections/2026/<Primary_Results\|general_Results>/gen_results_2026_4_<CD>.html` | yes | yes | yes (Early/ED/Mail/Prov) | yes (2026 primary pages) |
| MA | PD43+ ElectionStats | partial (CSV, live cadence unconfirmed) | `electionstats.state.ma.us/elections/download/<id>/precincts_include:0/` | town and precinct | yes | no | yes (2024 CSV) |
| MI | State site Akamai-denied; counties report separately | no | blocked | n/a | n/a | n/a | no |
| MN | electionresults.sos.mn.gov, Radware CAPTCHA | no from here | blocked | n/a | n/a | n/a | no |
| MS | PDFs only (sos.ms.gov) | no | none | PDFs | PDFs | no | no |
| MO | enr.sos.mo.gov, Cloudflare 1005 | no from here | `enr.sos.mo.gov/default.aspx` (blocked) | n/a | n/a | n/a | no |

Counts: **yes 9** (CA, CT, FL, GA, HI, ID, IL, IN, LA), **partial 6** (AL, CO, DE, IA, MA, MD), **no 10** (AK, AZ, AR, KS, KY, ME, MI, MN, MS, MO).

---

## AL Alabama
- Site: `https://www2.alabamavotes.gov/electionNight/` (SOS, custom ASP.NET WebForms). Pages: `statewideResultsByContest.aspx` (200, 42 KB) and `countyResultsByContest.aspx` (200). The SOS said for the May 2026 primary that county results were posted there with "Last Updated", turnout and "Boxes Reported" fields (from a news search, not fetched).
- Machine-readable: none found. HTML scrape only. The pages return a template with no data until an election is live, so I could not confirm the table structure. Sample: `samples/AL/statewide.html`.
- Granularity and vote type: statewide and county. House by district and vote type unknown. "Boxes Reported" works as a precincts-reporting denominator.
- Notes: reported to be slow on election night. No robots/WAF block seen. Races: Senate (open seat), Governor, 7 House seats.

## AK Alaska
- Site: `https://www.elections.alaska.gov/results/<yy>GENR/` (older pattern: `24PRIM/HD12.pdf`), Division of Elections.
- Every request to elections.alaska.gov returns HTTP 405 with `x-amzn-waf-action: captcha` (AWS WAF CAPTCHA), including PDFs. Not bypassed. Could not determine the format.
- Notes (search results, not fetched): only first-choice totals on election night, absentee and ranked-choice tabulation about 15 days later. Alaska counts slowly, so projections need a late-ballot model. Races: Senate, Governor, 1 at-large House seat.

## AZ Arizona
- Site: `https://results.arizona.vote/` (SOS). Cloudflare managed challenge ("Just a moment...", `cf-mitigated: challenge`, HTTP 403). Not bypassed. No other format found. The 2020 results were published as a zipped XML detail file (search result).
- Notes: heavy early-ballot dumps and late mail drop-off ballots, so counting runs for days. Counties publish their own results. Races: Governor, 9 House seats, no Senate race.

## AR Arkansas
- Presumed platform: Clarity ENR `https://results.enr.clarityelections.com/AR/`. It returns an nginx 403 (107 bytes) for the page and for `elections.json`, while other states return 200 on the same host. This looks like a state-specific rule. KY and AZ behave the same way.
- Not verified. Counties publish PDFs (Pulaski, Crawford). Races: Senate, Governor, 4 House seats.

## CA California (verified)
- Site: `https://electionresults.sos.ca.gov/` (redirects to the prior-elections page between elections). The data comes from `https://api.sos.ca.gov/returns/...`.
- Endpoints that returned 200 JSON (live-configured for Nov 3 2026, all zeros, "0% (0 of 23,860) precincts reporting"):
  - `/returns/governor` (statewide)
  - `/returns/governor/county/<county-slug>` (e.g. `kern`, `los-angeles`; returns a one-element array)
  - `/returns/us-rep/district/<N>` for N = 1 to 52. District 53 returned 500, and `/returns/us-house`, `/returns/us-senate`, `/returns/us-rep` returned 500 (no such route; there is no CA Senate race in 2026).
  - `/returns/secretary-of-state/county/kern` (other statewide offices follow the same slug pattern, unconfirmed)
- Fields: `raceTitle`, `Reporting` (string "x% (n of N) precincts reporting"), `ReportingTime`, `candidates[]` with `Name`, `Party`, `Votes`, `Percent`, `incumbent`.
- Granularity: statewide, county, and House district-wide. No vote-type split. Precincts reporting is a string that needs parsing.
- Notes: counting is slow. Mail ballots arrive and are counted for weeks and the update schedule is about every 15 to 60 minutes (the SOS says refresh is periodic). The API root returns 403 "Missing Authentication Token" (no index route). No robots.txt. Samples: `samples/CA/`.

## CO Colorado
- Site: `https://results.enr.clarityelections.com/CO/` (Clarity ENR). Mapthemidterms lists it as JSON.
- Verified: `https://results.enr.clarityelections.com/CO/elections.json` returns the election list (2026 Primary EID 126592, 2024 General EID 122598, etc.). The Nov 2026 general is not listed yet.
- Blocked here: data files such as `/CO/<EID>/current_ver.txt` return HTTP 202 with `x-amzn-waf-action: challenge` and an empty body (AWS WAF JS challenge). A HEAD request returns 200, but GET is challenged. Not bypassed. So the version-then-JSON path (`/CO/<EID>/<ver>/json/...`) is unconfirmed here.
- Granularity (platform standard): statewide and county, House by district, vote-type breakdown (Clarity detail). Counties also have their own Clarity sites (pattern `results.enr.clarityelections.com/CO/<County>/<EID>/`, unconfirmed).
- Notes: all-mail state, so most votes come in early and the count is quick. Races: Senate, Governor, 8 House seats. Samples: `samples/CO/elections.json`.

## CT Connecticut (verified)
- Site: `https://ctemspublic.pcctg.net/` (CTEMS public reporting, Angular; `electionhistory.ct.gov` is only the historical database). Election night data are static JSON files:
  - `https://ctemspublic.pcctg.net/ng-app/data/Elections.json` lists elections. ID 108 = "11/03/2026 -- November 2026 State Election" (default). ID 91 = 2024 presidential.
  - `.../ng-app/data/election/<id>/Version.json` returns `{"Version":N}` (108 is at 50647 now).
  - `.../ng-app/data/election/<id>/<Version>/{Lookupdata,Electiondata,stateVotes_Electiondata,townVotes_Electiondata,townStatus_Electiondata,voterTurnout_Electiondata}.json`
- Read order: Version.json first, then the versioned folder. Candidates and offices are numeric ids resolved through `Lookupdata.json`.
- Granularity: statewide, town (169 towns), no precinct. Per-town status string "7 of 7 (100.00%)" precincts reporting plus the "( Official Results )" tag. `Electiondata.json` has `PR` (precincts reported "759 of 759"), registered voters `RV`, ballots cast `BC`, turnout. `voterTurnout` gives per town ABR/ABC (absentee), EBR/EBC (early) and EDR/EDC (election day) issued/counted.
- Notes: no Senate race. Races: Governor, 5 House seats. Samples: `samples/CT/` (108 = Nov 2026 zeros, 91 = 2024 full).

## DE Delaware
- Site: `https://elections.delaware.gov/results/enr/PR2026.html` is the 2026 primary page (static HTML, 4 MB, 3,800 tables, "Data as of ... PM", "530 of 530 election districts reporting"). The general page would presumably be `GE2026.html` (404 today). There is also a Power BI report on the same page.
- Machine-readable: none; HTML tables only. The state says the reporting count covers early and election-day votes and not absentee tabulation.
- Notes: Senate (Coons), at-large House seat. No governor race in 2026. Sample: `samples/DE/PR2026_head.html`. No robots restrictions of concern.

## FL Florida (verified)
- Primary site: `https://results.elections.myflorida.com/`. Legacy ASP app still serving 2026 (I downloaded the 2026-08-18 primary file, 975 KB).
- Feed: form page `DownloadResults.asp?ElectionDate=11/5/2024&DATAMODE=`, then **POST** to `https://results.elections.myflorida.com/ResultsExtract.Asp` with `ElectionDate=<m/d/yyyy>&OfficialResults=Y&PartyRaces=N&DataMode=&FormsButton2=Download`. It returns tab-separated text with columns `ElectionDate, PartyCode, PartyName, RaceCode, OfficeDesc, CountyCode, CountyName, Juris1num, Juris2num, Precincts, PrecinctsReporting, CanNameLast, CanNameFirst, CanNameMiddle, CanVotes`.
- Granularity: county level, with `Precincts` and `PrecinctsReporting` per county and race. House rows have `RaceCode=USR` and the district in `Juris1num` (2024 file: 603 PRE rows, 402 USS rows, 211 USR rows). No vote-type split. The file is large and encoded Latin-1.
- For the unofficial election-night file, the `OfficialResults` flag should be set to `N` (unconfirmed for Nov 2026).
- Second source: `https://floridaelectionwatch.gov/` (TSV per mapthemidterms) is behind a Cloudflare challenge here, so unconfirmed.
- Notes: fast count, mail and early ballots reported first. Races: Governor, Senate special, 28 House seats. Sample: `samples/FL/sample_head.txt` (2024 general).

## GA Georgia (verified)
- Site: `https://results.sos.ga.gov/results/public/Georgia` (Enhanced Voting "results/public" Angular app).
- JSON API (no key):
  - `/results/public/api/jurisdictions/Georgia` lists elections (`publicElectionId`). The Nov 2026 general is not listed yet. Last Nov election id was `2024NovGen`.
  - `/results/public/api/elections/Georgia/<id>` (meta, report categories, `countGroups` = vote types)
  - `/results/public/api/elections/Georgia/<id>/ballot-items` (295 items in 2024, with `summaryResults.ballotOptions[].voteCount`, `groupResults[]`, `reportingStatus{reportingUnits,totalUnits,asOf}`)
  - `/results/public/api/elections/Georgia/<id>/localities` (counties)
  - Bulk export: `/cdn/results/Georgia/export-<id>.json` (33 MB, 2024) and `.zip` (1.4 MB).
- Vote types: Election Day, Advanced Voting, Absentee by Mail, Provisional (`groupResults`). Reporting denominator: `reportingUnits/totalUnits` (counties). House by district: yes ("US House of Representatives - District N").
- Notes: absentee and early are reported first. Fulton and Atlanta-area counties can report late. Races: Senate (Ossoff), Governor, 14 House seats. Counties also appear on the same host as `/results/public/<county-slug>/elections/<id>`; some county sites use Clarity. The Clarity GA root returns 403 for pages. Samples: `samples/GA/ballot-items.json` (2024).

## HI Hawaii (verified)
- Site: `https://elections.hawaii.gov/election-results/`. Machine file: `https://elections.hawaii.gov/wp-content/results/<Election name>/media.txt` (e.g. `2026 Primary/media.txt`, 2 MB tab-separated, UTF-16 in the 2024 file).
- Columns: Precinct_Name, Split_Name, precinct_splitId, Reg_voters, Ballots, Reporting, Contest_id, Contest_title, Contest_party, Choice_id, Candidate_name, Choice_party, Candidate_Type, Mail votes, In-Person votes. Rows are per precinct (the 2026 primary file has 'U.S. Representative, Dist II', Governor, etc.).
- Vote type: Mail vs In-Person. Reporting: per-precinct flag.
- Notes: polls close 7 pm HST = midnight ET, and the first printout is mostly mail ballots. Races: Governor, 2 House seats, no Senate. General path likely `.../2026 General/media.txt` (not yet present; unconfirmed). Sample: `samples/HI/media_2026P_head.txt`. robots.txt does not block `/wp-content/results/`.

## ID Idaho (verified)
- Site: `https://results.voteidaho.gov/results/public/id` (Enhanced Voting, same API as GA).
- Live-configured: `https://results.voteidaho.gov/results/public/api/elections/id/nov2026` (200, "General Election - November 3, 2026", `isOfficialResults:false`, `asOf 2026-10-30`). Ballot items: `.../api/elections/id/nov2026/ballot-items` (US Senator, House 1 and 2, Governor, statewide offices, ballot measures; 44 counties, `totalUnits` 44, 0 reporting). Election list: `/api/jurisdictions/id`.
- Granularity: statewide, county; vote types via the same `groupResults` mechanism (not populated yet). Bulk export link available from `mediaExportPath` in the jurisdiction response.
- Notes: results not posted until all polls close (north Idaho polls close later, 11 pm ET). Races: Senate (Risch), Governor, 2 House seats. Samples: `samples/ID/`.

## IL Illinois (verified)
- Site: `https://www.elections.il.gov/electionoperations/ElectionVoteTotals.aspx` (ISBE, ASP.NET).
- Per-office CSV download pattern (precinct level): `https://www.elections.il.gov/Downloads/ElectionOperations/ElectionResults/ByOffice/<electionId>/<electionId>-<contestId>-<OFFICE NAME>-<yyyy><GE|GP>.csv`, e.g. `66/66-250-1ST CONGRESS-2024GE.csv` (2024 general, 250 KB, 200) and `69/69-250-1ST CONGRESS-2026GP.csv` (2026 primary, 455 KB). Contest ids: Senate 150, Governor 180, AG 190, SOS 200, Comptroller 210, Treasurer 220, Congress 250 onward (+10 per district).
- Columns: JurisdictionID, JurisContainerID, JurisName, EISCandidateID, CandidateName, EISContestID, ContestName, PrecinctName, Registration, EISPartyID, PartyName, VoteCount (includes Under/Over votes rows).
- The 2026 general id is probably 70, and the file name suffix `2026GE`, but both returned 404 today (not published). No vote type split and no reporting flag in the CSV. Whether ISBE refreshes these files during election night is unconfirmed. The HTML page shows totals per race.
- robots.txt: `User-agent: *` with `Disallow: /` is present at www.elections.il.gov (the download URLs themselves returned 200). Treat as a polite-use constraint.
- Races: Senate (open seat), Governor, 17 House seats. Sample: `samples/IL/cd1_2026GP_head.csv`.

## IN Indiana (verified)
- Site: `https://enr.indianavoters.in.gov/site/index.html` (Indiana SOS ENR, AngularJS, static JSON on Azure Blob storage).
- Live-configured for Nov 3 2026: `https://enr.indianavoters.in.gov/site/data/settings.json` returns `CurrentElection: 11/03/2026`, `ElectionType: G`, `IntervalInMinutes: 2`, `VersionCode`, `VersionType: A`, `Certified: F`.
- Files are `data/<name>_<VersionType>.json`. Verified 200: `statewideElectionsC_A.json` (office list; `JurisdictionsReporting.TOTAL_ALLPRECINCTS: 5067`), `statewideElectionsR_A.json` (county list), `statewideTickerR_A.json`, `statewideTurnout_A.json` (per county `REGISTERED_VOTERS, VotersVoting, InPerson, Absentee`), `OffCatC_<officeCategoryId>_A.json` (US Representative category = 1005, one entry per district with candidates and `TOTAL`).
- Read `settings.json` first on every cycle, because the `VersionType` letter and `VersionCode` change as new data are published. County-level detail per race is probably in the same OffCat files or the map files (not confirmed with real votes).
- Notes: polls close 6 pm local (7 pm ET in most of the state, 6 pm ET in the Chicago-area and southwest counties on Central time). Races: 9 House seats, no Senate or governor. Samples: `samples/IN/`.

## IA Iowa
- Site: `https://electionresults.iowa.gov/IA/` (Clarity ENR). Mapthemidterms lists it as JSON.
- Verified: `https://electionresults.iowa.gov/IA/elections.json` (and the same on results.enr.clarityelections.com/IA) returns the list (2026 Primary EID 126082, 2024 General EID 122322). Nov 2026 not listed yet.
- Blocked here: data files (`/IA/<EID>/current_ver.txt`) return 202 with an AWS WAF challenge. Not bypassed.
- Races: Senate (open), Governor (open), 4 House seats. Counties have separate Clarity pages. Sample: `samples/IA/elections.json`.

## KS Kansas
- Election night page: `https://ent.sos.ks.gov/kssos_ent.html` (from a 2022 write-up; 105 per-county HTML pages; the author said it is not meant for programs and needs scraping). Starts about 5 pm on election day, unofficial; local races only on county sites.
- From here every request to `ent.sos.ks.gov` returns Cloudflare error 1009 (country ban). `sos.ks.gov` itself is reachable but the election-night link was not found there. Could not verify format or paths. The substack author also described a `wget -r` mirror (163 files).
- Notes: early totals are mostly advance votes. Races: Senate, Governor (open), 4 House seats.

## KY Kentucky
- Site: `https://vrsws.sos.ky.gov/liveresults/` (State Board of Elections "Election Night Reporting", search results; the county recap PDFs are on elect.ky.gov).
- Blocked: Akamai page "KY SBE Acceptable Use Policy ... identified website scraping activity originating from your IP". `elect.ky.gov` also returned 403 to the results path. Clarity KY path returns 403. Nothing else verified.
- Notes: the 2026 primary used precinct-level election-night PDFs by county. Races: Senate (open), 6 House seats.

## LA Louisiana (verified)
- Site: `https://voterportal.sos.la.gov/graphical` (SOS, AngularJS). Data host: `https://voterportal.sos.la.gov/ElectionResults/ElectionResults/Data?blob=<path>` (JSON despite the `.htm` names).
- Verified 200 JSON:
  - `blob=ElectionDates.htm` (default election 11/03/2026, id 344; also lists 06/27/2026 etc.) and `ElectionMode.htm`
  - `blob=20261103/RacesCandidates_Multiparish.htm` (race and candidate names: U.S. Senator "Jamie" Davis (DEM) vs Julia Letlow (REP), 6 House districts, etc.)
  - `blob=20261103/Votes_Multiparish.htm` (votes by race id: `PrecinctsReporting`, `PrecinctsExpected`, `NumAbsenteeReporting`, `NumAbsenteeExpected`, `VoterCountQualified`, `VoterCountVoted`, `Choice[].VoteTotal`, `Outcome`)
  - Same files for `20241105` return full 2024 results (verified).
  - Also seen in the app code (not fetched): `<date>/csv/ByParish_<raceId>.csv`, `csv/ByPrecinct_<raceId>.csv`, `VotesParish/Votes_...`, `VotesEarly/Votes_...`, `CurrentVersion.htm`.
- Vote type: early voting file exists and absentee reporting counts are included. Reporting denominator: precincts expected and reporting.
- Notes: statewide closed primaries for Congress happened in spring, so Nov has a different field. Races: Senate, 6 House seats. Samples: `samples/LA/`.

## ME Maine
- Site: `https://www.maine.gov/sos/cec/elec/results/index.html`. From here CloudFront returns "configured to block access from your country" (403). Could not verify anything.
- Notes: Maine uses ranked-choice voting for primaries and federal general races, so a RCV tabulation could extend past election night. Towns report to the state and results come out town by town. Races: Senate, Governor (open), 2 House seats.

## MD Maryland
- Site: `https://elections.maryland.gov/elections/2026/` (SBE static HTML). Primary 2026 results at `/elections/2026/Primary_Results/index.html` (index with status page, state offices, each Congress district `gen_results_2026_4_<CD>.html`).
- Verified (2026 primary): district page shows "Last refreshed: ...", "County Break Down (309 of 309 election day precincts reported)" and columns Early Voting, Election Day, Mail-In Ballot, Provisional, Total. No JSON or CSV links were found. The general pattern is probably `/elections/2026/general_Results/gen_results_2026_4_<CD>.html` (the 2024 folder exists as `/elections/2024/general_results/`, but I could not confirm file names).
- Notes: mail-in counting continues for days (the vote-type columns show it). Races: Governor, 8 House seats, no Senate. Sample: `samples/MD/cd1_primary.html`.

## MA Massachusetts
- Site: `https://electionstats.state.ma.us/` (PD43+ / ElectionStats by Civera). Verified CSV downloads for a past election: `https://electionstats.state.ma.us/elections/download/<electionId>/precincts_include:0/` (town level, 19 KB) and `precincts_include:1` (precinct level, 116 KB), e.g. id 165300 = 2024 President. Election ids come from `/elections/search/year_from:2026/year_to:2026/stage:General`. Page URL `/elections/view/<id>/`.
- Not confirmed: whether results are published live on election night in this system, and when the 2026 general entries (ids around 171923 and above exist for 2026) get created. Numbers carry thousands commas as strings.
- No vote-type split, no reporting flag in the CSV. Robots.txt allows all.
- Races: Senate (Markey), Governor, 9 House seats. Sample: `samples/MA/President_2024_town_165300.csv`.

## MI Michigan
- Statewide results: `https://mielections.us/election/results/` (did not resolve over HTTP from here) and michigan.gov/ElectionResults. `www.michigan.gov/sos/...` returns an Akamai "Access Denied" page. The state says clerks post unofficial results on their own sites and the state site is complete only about 24 hours after the polls close.
- No state-level live feed to read. Counties publish individually (many on Clarity or PDFs). Not verified.
- Notes: absentee ballots are processed before election day but big cities (Detroit) report late. Races: Senate (open), Governor (open), 13 House seats.

## MN Minnesota
- Site: `https://electionresults.sos.mn.gov/` (SOS). Every URL (including robots.txt) returns the Radware CAPTCHA page. Not bypassed, nothing verified. Mapthemidterms lists the format as "text" (the SOS publishes a semicolon-delimited media results file; I could not confirm paths).
- Notes: results are by precinct; counties report to the state. Races: Senate (open), Governor, 8 House seats.

## MS Mississippi
- Site: `https://www.sos.ms.gov/elections-voting/election-results`. Official results are PDFs per county (e.g. `elections/electionresults/2026MarchPrimary/Republican Primary/<County>.pdf`) and a statewide PDF. No state election-night reporting system found; media use AP and counties.
- Not machine-readable. Races: Senate (Hyde-Smith), 4 House seats. No governor race.

## MO Missouri
- Site: `https://enr.sos.mo.gov/default.aspx` (SOS Election Night Reporting, per a news article; the 2026 primary used it). `s1.sos.mo.gov` also redirects to results. From here Cloudflare returns error 1005 for both. Not verified.
- Notes: counties report to the state, statewide totals lag. Races: 8 House seats only (no Senate or governor in 2026).

---

## Cross-cutting findings for the projection
1. Good structured feeds I could fetch: CA, CT, FL, GA, HI, ID, IL, IN, LA. IN, ID, CT, LA and CA are already live-configured for Nov 3, so a fetcher can be tested now against the all-zero data.
2. The Enhanced Voting API (`/results/public/api/elections/<jurisdiction>/<id>/ballot-items`) is the same for GA and ID, and also serves UT per mapthemidterms. It gives vote-type splits and reporting units, so one parser covers several states.
3. Clarity (CO, IA, probably AR, KY): `elections.json` is open, the versioned data files are behind an AWS WAF challenge for non-browser clients. Needs a decision from Juan, not something to get around.
4. Reporting denominators: CA and FL (precincts), CT (precincts per town), GA/ID (counties), IN (5,067 precincts), LA (precincts and absentee boxes), MD (election-day precincts), HI (per-precinct flag). IL and MA CSVs have none.
5. Election-night timing caveats are from background knowledge, not tested: mail ballots lag in CA and AZ, slow counts in AK and ME (RCV), HI first printout is mail.
