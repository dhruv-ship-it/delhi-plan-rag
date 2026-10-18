# The eight test queries, every retrieval mode

Generated 2026-10-18 by `scripts/day2_queries.py`.

Eight queries, 4 modes each, top 5. 700 chunks indexed.

`dense` is nearest-neighbour search on the embeddings, `bm25` is keyword search, `hybrid` fuses the two with reciprocal rank fusion (k = 60). The tags after each result say where each index placed it: `d3` means dense rank 3, `b1` means BM25 rank 1, and a missing tag means that index did not return the chunk at all. Where `hybrid` beats both, it is because the two indexes agreed.

`hybrid+rerank` takes hybrid's top 20 and rescores them with the cross-encoder `Xenova/ms-marco-MiniLM-L-6-v2`. It is the only mode here that reads the query and the chunk **together**, so `rr` is its own rank and `rerank` is its score — an absolute judgement about this query and this chunk, unlike a fused score, which only encodes position (D-070, D-071). It is off in normal operation, because it costs 2.4 s a query against 0.031 s.

None of this is judged here. Read it and mark which results answer the question.

## 1. What is the minimum plot size for a TOD project?

### dense

1. `MPD47_GAZETTE_EN:4.2.3@p753:0` — clause 4.2.3, pages 753-754, [d1 b3 score 0.0164], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.3 TOD Norms
   - (v) Ground Coverage: Maximum ground coverage of 40% shall be permitted in the proposed development on TOD Plot. However, relaxations in ground coverag...
2. `MPD47_FAQ:Q14@p13:0` — clause Q14, pages 13-13, [d2 score 0.0161], zone_primary tod
   - path: FAQs - Transit Oriented Development (TOD) Policy › Q14. What is the Parking Provisions for TOD Projects?
   - Q14. What is the Parking Provisions for TOD Projects? TOD Plot shall provide 1 Equivalent Car Space (ECS) per100 sqm. of FAR area.
3. `MPD47_FAQ:Q13@p13:0` — clause Q13, pages 13-13, [d3 score 0.0159], zone_primary tod
   - path: FAQs - Transit Oriented Development (TOD) Policy › Q13. What is the maximum ground coverage permissible for a TOD Plot?
   - Q13. What is the maximum ground coverage permissible for a TOD Plot? Maximum permissible ground coverage is 40%.
4. `MPD47_FAQ:Q3@p11:0` — clause Q3, pages 11-11, [d4 b8 score 0.0156], zone_primary tod
   - path: FAQs - Transit Oriented Development (TOD) Policy › Q3. What is the eligibility criteria?
   - Q3. What is the eligibility criteria? i. Minimum plot area of 2000 sqm. accessible from an existing road having a minimum ROW of 18m or proposed conti...
5. `MPD47_FAQ:Q5@p15:0` — clause Q5, pages 15-15, [d5 b10 score 0.0154], zone_primary hdc
   - path: FAQs on High Density Corridor (HDC) Policy › Q5. What is the minimum plot size requirement to enter the scheme?
   - Q5. What is the minimum plot size requirement to enter the scheme? The original plot must have a minimum area of 8,000 sqm, and the resulting final HD...

### bm25

1. `MPD47_GAZETTE_EN:4.2.3@p751:0` — clause 4.2.3, pages 751-752, [d6 b1 score 0.0164], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.3 TOD Norms
   - 4.2.3 TOD Norms (i) Participation in TOD Policy is voluntary. In case of TOD Plots, the existing Land Use shall stand superseded, as per the sanctione...
2. `MPD47_GAZETTE_EN:4.2.3@p752:1` — clause 4.2.3, pages 752-753, [d8 b2 score 0.0161], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.3 TOD Norms
   - (b) The permissible mix of uses for each plot in a TOD Zone shall be as below: i. A minimum 65% of the total permissible FAR shall be earmarked for Re...
3. `MPD47_GAZETTE_EN:4.2.3@p753:0` — clause 4.2.3, pages 753-754, [d1 b3 score 0.0159], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.3 TOD Norms
   - (v) Ground Coverage: Maximum ground coverage of 40% shall be permitted in the proposed development on TOD Plot. However, relaxations in ground coverag...
4. `MPD47_GAZETTE_EN:4.3.3@p758:0` — clause 4.3.3, pages 758-759, [b4 score 0.0156], zone_primary hdc
   - path: 4.3 HIGH DENSITY CORRIDOR DEVELOPMENT › 4.3.3 HDC Norms
   - 4.3.3 HDC Norms (i) Participation in the HDC Policy is voluntary. In case of HDC Plots, the land use shall be as per the sanctioned HDC project. Preva...
5. `MPD47_GAZETTE_EN:4.6.4@p781:0` — clause 4.6.4, pages 781-782, [d24 b5 score 0.0154]
   - path: 4.6 REGENERATION OF UN-PLANNED AREAS › 4.6.4 Slum and Jhuggi Jhopri (JJ) Clusters
   - (a) General controls: i. The Rehabilitation plot area shall not be less than 40% of the total plot area. Rest of the plot area may be utilised for rem...

### hybrid

1. `MPD47_GAZETTE_EN:4.2.3@p753:0` — clause 4.2.3, pages 753-754, [d1 b3 score 0.0323], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.3 TOD Norms
   - (v) Ground Coverage: Maximum ground coverage of 40% shall be permitted in the proposed development on TOD Plot. However, relaxations in ground coverag...
2. `MPD47_GAZETTE_EN:4.2.3@p751:0` — clause 4.2.3, pages 751-752, [d6 b1 score 0.0315], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.3 TOD Norms
   - 4.2.3 TOD Norms (i) Participation in TOD Policy is voluntary. In case of TOD Plots, the existing Land Use shall stand superseded, as per the sanctione...
3. `MPD47_GAZETTE_EN:4.2.3@p752:1` — clause 4.2.3, pages 752-753, [d8 b2 score 0.0308], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.3 TOD Norms
   - (b) The permissible mix of uses for each plot in a TOD Zone shall be as below: i. A minimum 65% of the total permissible FAR shall be earmarked for Re...
4. `MPD47_FAQ:Q3@p11:0` — clause Q3, pages 11-11, [d4 b8 score 0.0303], zone_primary tod
   - path: FAQs - Transit Oriented Development (TOD) Policy › Q3. What is the eligibility criteria?
   - Q3. What is the eligibility criteria? i. Minimum plot area of 2000 sqm. accessible from an existing road having a minimum ROW of 18m or proposed conti...
5. `MPD47_GAZETTE_EN:4.2.3@p752:0` — clause 4.2.3, pages 752-752, [d7 b7 score 0.0299], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.3 TOD Norms
   - (iv) FAR (a) FAR of TOD Plot shall be as follows: i. Base FAR shall be 400 subject to payment of TOD charges, as notified from time to time. ii. TOD C...

### hybrid+rerank

1. `MPD47_GAZETTE_EN:4.2.3@p753:0` — clause 4.2.3, pages 753-754, [d1 b3 score 0.0323], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.3 TOD Norms
   - (v) Ground Coverage: Maximum ground coverage of 40% shall be permitted in the proposed development on TOD Plot. However, relaxations in ground coverag...
2. `MPD47_GAZETTE_EN:4.2.3@p751:0` — clause 4.2.3, pages 751-752, [d6 b1 score 0.0315], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.3 TOD Norms
   - 4.2.3 TOD Norms (i) Participation in TOD Policy is voluntary. In case of TOD Plots, the existing Land Use shall stand superseded, as per the sanctione...
3. `MPD47_GAZETTE_EN:4.2.3@p752:1` — clause 4.2.3, pages 752-753, [d8 b2 score 0.0308], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.3 TOD Norms
   - (b) The permissible mix of uses for each plot in a TOD Zone shall be as below: i. A minimum 65% of the total permissible FAR shall be earmarked for Re...
4. `MPD47_FAQ:Q3@p11:0` — clause Q3, pages 11-11, [d4 b8 score 0.0303], zone_primary tod
   - path: FAQs - Transit Oriented Development (TOD) Policy › Q3. What is the eligibility criteria?
   - Q3. What is the eligibility criteria? i. Minimum plot area of 2000 sqm. accessible from an existing road having a minimum ROW of 18m or proposed conti...
5. `MPD47_GAZETTE_EN:4.2.3@p752:0` — clause 4.2.3, pages 752-752, [d7 b7 score 0.0299], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.3 TOD Norms
   - (iv) FAR (a) FAR of TOD Plot shall be as follows: i. Base FAR shall be 400 subject to payment of TOD charges, as notified from time to time. ii. TOD C...

## 2. How wide is the TOD zone around a metro line?

### dense

1. `MPD47_FAQ:Q1@p11:0` — clause Q1, pages 11-11, [d1 b1 score 0.0164], zone_primary tod
   - path: FAQs - Transit Oriented Development (TOD) Policy › Q1. What is TOD Zone?
   - Q1. What is TOD Zone? TOD Zone is the area falling under 500m wide corridor on either side of centreline of the existing and planned/approved Metro Co...
2. `MPD47_GAZETTE_EN:4.2.1:0` — clause 4.2.1, pages 750-751, [d2 b2 score 0.0161], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.1 Definitions
   - 4.2.1 Definitions (i) “TOD Zone”: area under 500m wide corridor on either side of centreline of the existing and planned/approved Metro Corridors/Rout...
3. `MPD47_FAQ:Q14@p13:0` — clause Q14, pages 13-13, [d3 score 0.0159], zone_primary tod
   - path: FAQs - Transit Oriented Development (TOD) Policy › Q14. What is the Parking Provisions for TOD Projects?
   - Q14. What is the Parking Provisions for TOD Projects? TOD Plot shall provide 1 Equivalent Car Space (ECS) per100 sqm. of FAR area.
4. `MPD47_GAZETTE_EN:4.2.3@p753:0` — clause 4.2.3, pages 753-754, [d4 b27 score 0.0156], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.3 TOD Norms
   - (v) Ground Coverage: Maximum ground coverage of 40% shall be permitted in the proposed development on TOD Plot. However, relaxations in ground coverag...
5. `MPD47_GAZETTE_EN:4.2.3@p751:0` — clause 4.2.3, pages 751-752, [d5 b15 score 0.0154], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.3 TOD Norms
   - 4.2.3 TOD Norms (i) Participation in TOD Policy is voluntary. In case of TOD Plots, the existing Land Use shall stand superseded, as per the sanctione...

### bm25

1. `MPD47_FAQ:Q1@p11:0` — clause Q1, pages 11-11, [d1 b1 score 0.0164], zone_primary tod
   - path: FAQs - Transit Oriented Development (TOD) Policy › Q1. What is TOD Zone?
   - Q1. What is TOD Zone? TOD Zone is the area falling under 500m wide corridor on either side of centreline of the existing and planned/approved Metro Co...
2. `MPD47_GAZETTE_EN:4.2.1:0` — clause 4.2.1, pages 750-751, [d2 b2 score 0.0161], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.1 Definitions
   - 4.2.1 Definitions (i) “TOD Zone”: area under 500m wide corridor on either side of centreline of the existing and planned/approved Metro Corridors/Rout...
3. `MPD47_GAZETTE_EN:3.6.1@p721:1` — clause 3.6.1, pages 721-723, [d15 b3 score 0.0159]
   - path: 3.6 TRANSPORT & MOBILITY › 3.6.1 Transport Infrastructure and Connectivity
   - (j) In order to improve the utilisation of public transport, concerned transit agencies may consider the following: i. Transit stations shall be acces...
4. `MPD47_GAZETTE_EN:4.2.4@p755:0` — clause 4.2.4, pages 755-756, [d13 b4 score 0.0156], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.4 Framework for Implementation of the Policy
   - (e) The TOD Project proposal shall comply with mandatory sustainability provisions/Green Building Norms given in the prevailing MPD and UBBL w.r.t. Wa...
5. `MPD47_GAZETTE_EN:p1140:0` — clause (none), pages 1140-1141, [b5 score 0.0154]
   - path: 6. SERVICE PLAN - DEPARTMENT OF ENVIRONMENT, GNCTD
   - | | | | | | | P-I (Narela Sub-city). | required 32 mtr. | | --- | --- | --- | --- | --- | --- | --- | --- | | 3. | | 220/66kV (800 MVA) | Bankner Vill...

### hybrid

1. `MPD47_FAQ:Q1@p11:0` — clause Q1, pages 11-11, [d1 b1 score 0.0328], zone_primary tod
   - path: FAQs - Transit Oriented Development (TOD) Policy › Q1. What is TOD Zone?
   - Q1. What is TOD Zone? TOD Zone is the area falling under 500m wide corridor on either side of centreline of the existing and planned/approved Metro Co...
2. `MPD47_GAZETTE_EN:4.2.1:0` — clause 4.2.1, pages 750-751, [d2 b2 score 0.0323], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.1 Definitions
   - 4.2.1 Definitions (i) “TOD Zone”: area under 500m wide corridor on either side of centreline of the existing and planned/approved Metro Corridors/Rout...
3. `MPD47_FAQ:Q15@p13:0` — clause Q15, pages 13-13, [d8 b7 score 0.0296], zone_primary tod
   - path: FAQs - Transit Oriented Development (TOD) Policy › Q15. Whether TOD Projects shall be allowed along proposed/ under construction
   - Q15. Whether TOD Projects shall be allowed along proposed/ under construction Metro Corridors/Routes and regional and interstate mass transit stations...
4. `MPD47_GAZETTE_EN:4.2.4@p755:0` — clause 4.2.4, pages 755-756, [d13 b4 score 0.0293], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.4 Framework for Implementation of the Policy
   - (e) The TOD Project proposal shall comply with mandatory sustainability provisions/Green Building Norms given in the prevailing MPD and UBBL w.r.t. Wa...
5. `MPD47_GAZETTE_EN:3.6.1@p721:1` — clause 3.6.1, pages 721-723, [d15 b3 score 0.0292]
   - path: 3.6 TRANSPORT & MOBILITY › 3.6.1 Transport Infrastructure and Connectivity
   - (j) In order to improve the utilisation of public transport, concerned transit agencies may consider the following: i. Transit stations shall be acces...

### hybrid+rerank

1. `MPD47_FAQ:Q1@p11:0` — clause Q1, pages 11-11, [d1 b1 rr1 rerank +8.14 score 0.0328], zone_primary tod
   - path: FAQs - Transit Oriented Development (TOD) Policy › Q1. What is TOD Zone?
   - Q1. What is TOD Zone? TOD Zone is the area falling under 500m wide corridor on either side of centreline of the existing and planned/approved Metro Co...
2. `MPD47_GAZETTE_EN:4.2.1:0` — clause 4.2.1, pages 750-751, [d2 b2 rr2 rerank +5.61 score 0.0323], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.1 Definitions
   - 4.2.1 Definitions (i) “TOD Zone”: area under 500m wide corridor on either side of centreline of the existing and planned/approved Metro Corridors/Rout...
3. `MPD47_GAZETTE_EN:4.2.4@p755:0` — clause 4.2.4, pages 755-756, [d13 b4 rr3 rerank -0.88 score 0.0293], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.4 Framework for Implementation of the Policy
   - (e) The TOD Project proposal shall comply with mandatory sustainability provisions/Green Building Norms given in the prevailing MPD and UBBL w.r.t. Wa...
4. `MPD47_GAZETTE_EN:11.1.1@p851:0` — clause 11.1.1, pages 851-852, [d21 b8 rr4 rerank -1.24 score 0.0271]
   - path: 11.1 Transportation › 11.1.1 Development Control Norms (DCN)
   - 11.1 Transportation 11.1.1 Development Control Norms (DCN) | Sl. No. | Use Premise | Min. Plot Area | Area under Building (%) (Max.) | Max. FAR* | Max...
5. `MPD47_FAQ:Q3@p11:0` — clause Q3, pages 11-11, [d7 b18 rr5 rerank -1.61 score 0.0277], zone_primary tod
   - path: FAQs - Transit Oriented Development (TOD) Policy › Q3. What is the eligibility criteria?
   - Q3. What is the eligibility criteria? i. Minimum plot area of 2000 sqm. accessible from an existing road having a minimum ROW of 18m or proposed conti...

## 3. Maximum ground coverage allowed for high density corridor projects

### dense

1. `MPD47_FAQ:Q16@p16:0` — clause Q16, pages 16-16, [d1 b16 score 0.0164], zone_primary hdc
   - path: FAQs on High Density Corridor (HDC) Policy › Q16. What are the ground coverage limits for different uses?
   - Q16. What are the ground coverage limits for different uses? Maximum ground coverage is 40% for Residential, Commercial, and PSP uses, and 70% for War...
2. `MPD47_GAZETTE_EN:4.3.3@p759:0` — clause 4.3.3, pages 759-760, [d2 b1 score 0.0161], zone_primary hdc
   - path: 4.3 HIGH DENSITY CORRIDOR DEVELOPMENT › 4.3.3 HDC Norms
   - (f) Vertical mix of uses shall be allowed except in plots earmarked for Warehousing/Logistics use. Separate entry/exits and service cores shall have t...
3. `MPD47_GAZETTE_EN:4.2.3@p753:0` — clause 4.2.3, pages 753-754, [d3 b3 score 0.0159], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.3 TOD Norms
   - (v) Ground Coverage: Maximum ground coverage of 40% shall be permitted in the proposed development on TOD Plot. However, relaxations in ground coverag...
4. `MPD47_FAQ:Q13@p13:0` — clause Q13, pages 13-13, [d4 b11 score 0.0156], zone_primary tod
   - path: FAQs - Transit Oriented Development (TOD) Policy › Q13. What is the maximum ground coverage permissible for a TOD Plot?
   - Q13. What is the maximum ground coverage permissible for a TOD Plot? Maximum permissible ground coverage is 40%.
5. `MPD47_FAQ:Q17@p16:0` — clause Q17, pages 16-16, [d5 b7 score 0.0154], zone_primary hdc
   - path: FAQs on High Density Corridor (HDC) Policy › Q17. Is relaxation in Ground Coverage provided?
   - Q17. Is relaxation in Ground Coverage provided? Relaxations in ground coverage for HDC Projects that are not able to utilise the permissible FAR due t...

### bm25

1. `MPD47_GAZETTE_EN:4.3.3@p759:0` — clause 4.3.3, pages 759-760, [d2 b1 score 0.0164], zone_primary hdc
   - path: 4.3 HIGH DENSITY CORRIDOR DEVELOPMENT › 4.3.3 HDC Norms
   - (f) Vertical mix of uses shall be allowed except in plots earmarked for Warehousing/Logistics use. Separate entry/exits and service cores shall have t...
2. `MPD47_GAZETTE_EN:4.3.4@p762:0` — clause 4.3.4, pages 762-763, [b2 score 0.0161], zone_primary hdc
   - path: 4.3 HIGH DENSITY CORRIDOR DEVELOPMENT › 4.3.4 Framework for Implementation of the Policy
   - (e) The Committee shall meet regularly to fast track the approval process. The maximum time limit for approval of the HDC Project shall be 60 days, fr...
3. `MPD47_GAZETTE_EN:4.2.3@p753:0` — clause 4.2.3, pages 753-754, [d3 b3 score 0.0159], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.3 TOD Norms
   - (v) Ground Coverage: Maximum ground coverage of 40% shall be permitted in the proposed development on TOD Plot. However, relaxations in ground coverag...
4. `MPD47_GAZETTE_EN:4.3@p757:0` — clause 4.3, pages 757-757, [d6 b4 score 0.0156], zone_primary hdc
   - path: 4.3 HIGH DENSITY CORRIDOR DEVELOPMENT
   - 4.3 HIGH DENSITY CORRIDOR DEVELOPMENT High Density Corridor (HDC) Zone is envisioned to optimize land use efficiency by promoting compact, mixed-use a...
5. `MPD47_GAZETTE_EN:1.7.1@p666:0` — clause 1.7.1, pages 666-666, [d11 b5 score 0.0154]
   - path: 1.7 Land Use Plan for NCT of Delhi › 1.7.1 Land Use Plan
   - (d) High Density Corridor (HDC) Zone: HDC Zones, covering approximately 20 sq. km along the executed stretch of the Urban Extension Road-II (UER-II), ...

### hybrid

1. `MPD47_GAZETTE_EN:4.3.3@p759:0` — clause 4.3.3, pages 759-760, [d2 b1 score 0.0325], zone_primary hdc
   - path: 4.3 HIGH DENSITY CORRIDOR DEVELOPMENT › 4.3.3 HDC Norms
   - (f) Vertical mix of uses shall be allowed except in plots earmarked for Warehousing/Logistics use. Separate entry/exits and service cores shall have t...
2. `MPD47_GAZETTE_EN:4.2.3@p753:0` — clause 4.2.3, pages 753-754, [d3 b3 score 0.0317], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.3 TOD Norms
   - (v) Ground Coverage: Maximum ground coverage of 40% shall be permitted in the proposed development on TOD Plot. However, relaxations in ground coverag...
3. `MPD47_GAZETTE_EN:4.3@p757:0` — clause 4.3, pages 757-757, [d6 b4 score 0.0308], zone_primary hdc
   - path: 4.3 HIGH DENSITY CORRIDOR DEVELOPMENT
   - 4.3 HIGH DENSITY CORRIDOR DEVELOPMENT High Density Corridor (HDC) Zone is envisioned to optimize land use efficiency by promoting compact, mixed-use a...
4. `MPD47_FAQ:Q17@p16:0` — clause Q17, pages 16-16, [d5 b7 score 0.0303], zone_primary hdc
   - path: FAQs on High Density Corridor (HDC) Policy › Q17. Is relaxation in Ground Coverage provided?
   - Q17. Is relaxation in Ground Coverage provided? Relaxations in ground coverage for HDC Projects that are not able to utilise the permissible FAR due t...
5. `MPD47_FAQ:Q13@p13:0` — clause Q13, pages 13-13, [d4 b11 score 0.0297], zone_primary tod
   - path: FAQs - Transit Oriented Development (TOD) Policy › Q13. What is the maximum ground coverage permissible for a TOD Plot?
   - Q13. What is the maximum ground coverage permissible for a TOD Plot? Maximum permissible ground coverage is 40%.

### hybrid+rerank

1. `MPD47_GAZETTE_EN:4.2.3@p753:0` — clause 4.2.3, pages 753-754, [d3 b3 rr1 rerank +4.97 score 0.0317], zone_primary tod
   - path: 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) › 4.2.3 TOD Norms
   - (v) Ground Coverage: Maximum ground coverage of 40% shall be permitted in the proposed development on TOD Plot. However, relaxations in ground coverag...
2. `MPD47_FAQ:Q13@p13:0` — clause Q13, pages 13-13, [d4 b11 rr2 rerank +3.35 score 0.0297], zone_primary tod
   - path: FAQs - Transit Oriented Development (TOD) Policy › Q13. What is the maximum ground coverage permissible for a TOD Plot?
   - Q13. What is the maximum ground coverage permissible for a TOD Plot? Maximum permissible ground coverage is 40%.
3. `MPD47_FAQ:Q16@p16:0` — clause Q16, pages 16-16, [d1 b16 rr3 rerank +3.27 score 0.0296], zone_primary hdc
   - path: FAQs on High Density Corridor (HDC) Policy › Q16. What are the ground coverage limits for different uses?
   - Q16. What are the ground coverage limits for different uses? Maximum ground coverage is 40% for Residential, Commercial, and PSP uses, and 70% for War...
4. `MPD47_GAZETTE_EN:11.1.1@p855:0` — clause 11.1.1, pages 855-856, [d28 b26 rr4 rerank +2.22 score 0.0230]
   - path: 11.1 Transportation › 11.1.1 Development Control Norms (DCN)
   - (d) Fuel stations shall be regulated by the following controls: i. Fuels stations shall be located on ROW not less than 24 m. ii. The maximum ground c...
5. `MPD47_FAQ:Q3@p18:0` — clause Q3, pages 18-18, [d9 b20 rr5 rerank +1.98 score 0.0270], zone_primary lda
   - path: FAQs on LDA › Q3. What are the permissible FAR, ground coverage and height for a Low Density
   - Q3. What are the permissible FAR, ground coverage and height for a Low Density Plot? The Development Control Norms applicable to each Use Premise with...

## 4. Can a fuel station be built in Zone O?

### dense

1. `MPD47_GAZETTE_EN:11.1.1@p855:0` — clause 11.1.1, pages 855-856, [d1 b2 score 0.0164]
   - path: 11.1 Transportation › 11.1.1 Development Control Norms (DCN)
   - (d) Fuel stations shall be regulated by the following controls: i. Fuels stations shall be located on ROW not less than 24 m. ii. The maximum ground c...
2. `MPD47_GAZETTE_EN:Annexure 18:0` — clause Annexure 18, pages 961-962, [d2 b7 score 0.0161]
   - path: Annexure 18: Residential Use Zone - List of Use Premises permitted and Use Premises –
   - Annexure 18: Residential Use Zone - List of Use Premises permitted and Use Premises – not permitted: | RESIDENTIAL | | | --- | --- | | Use Premises – ...
3. `MPD47_GAZETTE_EN:9.4:0` — clause 9.4, pages 840-840, [d3 score 0.0159]
   - path: 9.4 Conditions for approval of layout plans for Industrial Use Zone:
   - 9.4 Conditions for approval of layout plans for Industrial Use Zone: (i) New Industrial areas should be located along major arterial roads. (ii) All n...
4. `MPD47_GAZETTE_EN:4.6.2@p777:0` — clause 4.6.2, pages 777-778, [d4 score 0.0156]
   - path: 4.6 REGENERATION OF UN-PLANNED AREAS › 4.6.2 Unauthorised Colonies (UCs)
   - | Sl. No. | Facility | Facilities built on separate plots | | | | --- | --- | --- | --- | --- | | | | Minimum Plot Area (sqm) | FAR | Ground Coverage ...
5. `MPD47_GAZETTE_EN:11.1.1@p854:0` — clause 11.1.1, pages 854-855, [d5 b1 score 0.0154]
   - path: 11.1 Transportation › 11.1.1 Development Control Norms (DCN)
   - (f) A single agency shall be responsible for management of the MLP and the on-street parking up to a distance of minimum 500 m from the ingress of the...

### bm25

1. `MPD47_GAZETTE_EN:11.1.1@p854:0` — clause 11.1.1, pages 854-855, [d5 b1 score 0.0164]
   - path: 11.1 Transportation › 11.1.1 Development Control Norms (DCN)
   - (f) A single agency shall be responsible for management of the MLP and the on-street parking up to a distance of minimum 500 m from the ingress of the...
2. `MPD47_GAZETTE_EN:11.1.1@p855:0` — clause 11.1.1, pages 855-856, [d1 b2 score 0.0161]
   - path: 11.1 Transportation › 11.1.1 Development Control Norms (DCN)
   - (d) Fuel stations shall be regulated by the following controls: i. Fuels stations shall be located on ROW not less than 24 m. ii. The maximum ground c...
3. `NGT_OA572_GNCTD_REPORT:11:0` — clause 11, pages 9-10, [b3 score 0.0159]
   - path: 11.
   - 11. The:committee was appraised that DDA in pursuance of Hon'ble:High Court in contempt case WP(C) 715/2015 and WP(C) 5751/2014 - Sh. Vijay Kumar Diwa...
4. `MPD47_GAZETTE_EN:Annexure 1@p932:1` — clause Annexure 1, pages 932-932, [b4 score 0.0156]
   - path: Annexure 1: List of Biodiversity parks and parks maintained by DDA
   - | 510 | Park & Waterbody at Dushghara, Todapur | 9.58 | | --- | --- | --- | | 541 | Amrut Bio-Diversity Park | 311.22 | | 542 | Green area at Yamuna B...
5. `MPD47_GAZETTE_EN:Annexure 19:0` — clause Annexure 19, pages 963-964, [d12 b5 score 0.0154]
   - path: Annexure 19: Commercial Use Zone: List of Use Premises permitted and Use Premises
   - Annexure 19: Commercial Use Zone: List of Use Premises permitted and Use Premises – not permitted: | COMMERCIAL | | | --- | --- | | Use Premises – Per...

### hybrid

1. `MPD47_GAZETTE_EN:11.1.1@p855:0` — clause 11.1.1, pages 855-856, [d1 b2 score 0.0325]
   - path: 11.1 Transportation › 11.1.1 Development Control Norms (DCN)
   - (d) Fuel stations shall be regulated by the following controls: i. Fuels stations shall be located on ROW not less than 24 m. ii. The maximum ground c...
2. `MPD47_GAZETTE_EN:11.1.1@p854:0` — clause 11.1.1, pages 854-855, [d5 b1 score 0.0318]
   - path: 11.1 Transportation › 11.1.1 Development Control Norms (DCN)
   - (f) A single agency shall be responsible for management of the MLP and the on-street parking up to a distance of minimum 500 m from the ingress of the...
3. `MPD47_GAZETTE_EN:Annexure 18:0` — clause Annexure 18, pages 961-962, [d2 b7 score 0.0311]
   - path: Annexure 18: Residential Use Zone - List of Use Premises permitted and Use Premises –
   - Annexure 18: Residential Use Zone - List of Use Premises permitted and Use Premises – not permitted: | RESIDENTIAL | | | --- | --- | | Use Premises – ...
4. `MPD47_GAZETTE_EN:Annexure 19:0` — clause Annexure 19, pages 963-964, [d12 b5 score 0.0293]
   - path: Annexure 19: Commercial Use Zone: List of Use Premises permitted and Use Premises
   - Annexure 19: Commercial Use Zone: List of Use Premises permitted and Use Premises – not permitted: | COMMERCIAL | | | --- | --- | | Use Premises – Per...
5. `MPD47_GAZETTE_EN:Annexure 20:0` — clause Annexure 20, pages 965-965, [d30 b20 score 0.0236]
   - path: Annexure 20: Industrial Use Zone: List of Use Premises permitted and Use Premises –
   - Annexure 20: Industrial Use Zone: List of Use Premises permitted and Use Premises – not permitted: | INDUSTRIAL | | | --- | --- | | Use Premises – Per...

### hybrid+rerank

1. `MPD47_GAZETTE_EN:11.1.1@p854:0` — clause 11.1.1, pages 854-855, [d5 b1 rr1 rerank +1.95 score 0.0318]
   - path: 11.1 Transportation › 11.1.1 Development Control Norms (DCN)
   - (f) A single agency shall be responsible for management of the MLP and the on-street parking up to a distance of minimum 500 m from the ingress of the...
2. `MPD47_GAZETTE_EN:11.1.1@p855:0` — clause 11.1.1, pages 855-856, [d1 b2 rr2 rerank +0.23 score 0.0325]
   - path: 11.1 Transportation › 11.1.1 Development Control Norms (DCN)
   - (d) Fuel stations shall be regulated by the following controls: i. Fuels stations shall be located on ROW not less than 24 m. ii. The maximum ground c...
3. `MPD47_GAZETTE_EN:12.3.2:0` — clause 12.3.2, pages 876-877, [b10 rr3 rerank -5.22 score 0.0143]
   - path: 12.3 PSP – Security-Police Facilities & Safety-Fire Facilities › 12.3.2 Development Control Norms (DCN)
   - 12.3.2 Development Control Norms (DCN) | Sl. No. | Use Premise | Plot Area (sqm)/unit | Max. Ground Coverage (%) | Max. FAR | Min. ROW (m) | Height (m...
4. `MPD47_GAZETTE_EN:8.3.2@p832:0` — clause 8.3.2, pages 832-833, [d6 rr4 rerank -5.65 score 0.0152]
   - path: 8.3 Hotel › 8.3.2 Development Control Norms (DCN)
   - (f) Hotels/budget hotels shall also be permitted in Commercial Centres in Industrial Use Zone, and Transport Nodes (ISBT, Bus Depot/Terminal, Railway ...
5. `MPD47_GAZETTE_EN:Annexure 19:0` — clause Annexure 19, pages 963-964, [d12 b5 rr5 rerank -6.16 score 0.0293]
   - path: Annexure 19: Commercial Use Zone: List of Use Premises permitted and Use Premises
   - Annexure 19: Commercial Use Zone: List of Use Premises permitted and Use Premises – not permitted: | COMMERCIAL | | | --- | --- | | Use Premises – Per...

## 5. Minimum plot area for redevelopment of commercial areas

### dense

1. `MPD47_FAQ:Q5@p2:0` — clause Q5, pages 2-3, [d1 b1 score 0.0164]
   - path: FAQs - GENERIC › Q5. What provisions have been made for redevelopment under different land
   - Q5. What provisions have been made for redevelopment under different land uses? MPD-2047 allows redevelopment at the plot level with following provisi...
2. `MPD47_GAZETTE_EN:4.6.5@p785:0` — clause 4.6.5, pages 785-785, [d2 score 0.0161]
   - path: 4.6 REGENERATION OF UN-PLANNED AREAS › 4.6.5 Non-conforming Industrial Areas
   - (b) Following development controls shall be permitted at plot level: i. Permissible FAR of 200, irrespective of plot size. ii. Maximum 10% of the perm...
3. `MPD47_GAZETTE_EN:4.5.3:0` — clause 4.5.3, pages 770-771, [d3 b8 score 0.0159]
   - path: 4.5 REGENERATION OF PLANNED AREAS › 4.5.3 Regeneration Area
   - 4.5.3 Regeneration Area (i) Conditions: (a) Minimum Plot area for undertaking regeneration shall be 3,000 sqm for Residential and 1,000 sqm for Commer...
4. `MPD47_FAQ:Q5@p19:0` — clause Q5, pages 19-19, [d4 b17 score 0.0156], zone_primary lda
   - path: FAQs on LDA › Q5. What is the minimum green area requirement for plots under Residential Use
   - Q5. What is the minimum green area requirement for plots under Residential Use Premises? A minimum of 50% of the total plot area shall be maintained a...
5. `MPD47_GAZETTE_EN:4.5.6:0` — clause 4.5.6, pages 772-772, [d5 score 0.0154]
   - path: 4.5 REGENERATION OF PLANNED AREAS › 4.5.6 Regeneration in Commercial Areas
   - 4.5.6 Regeneration in Commercial Areas (i) Regeneration schemes for District Centres, Community Centres, Local Shopping Centres, and Convenience Shopp...

### bm25

1. `MPD47_FAQ:Q5@p2:0` — clause Q5, pages 2-3, [d1 b1 score 0.0164]
   - path: FAQs - GENERIC › Q5. What provisions have been made for redevelopment under different land
   - Q5. What provisions have been made for redevelopment under different land uses? MPD-2047 allows redevelopment at the plot level with following provisi...
2. `MPD47_GAZETTE_EN:9.1.3:0` — clause 9.1.3, pages 837-837, [d9 b2 score 0.0161]
   - path: 9.1 Planned Industrial Area › 9.1.3 Permissible Uses for Use Conversion in Planned Industrial Areas
   - 9.1.3 Permissible Uses for Use Conversion in Planned Industrial Areas (i) Industrial units/plots shall be eligible for use conversion to Commercial Us...
3. `MPD47_GAZETTE_EN:8.1.2@p823:0` — clause 8.1.2, pages 823-824, [d13 b3 score 0.0159]
   - path: 8.1 General Business and Commerce › 8.1.2 Development Control Norms (DCN)
   - 8.1.2 Development Control Norms (DCN) (i) Convenience Shopping Centre (CSC) and Local Shopping Centre (LSC): Centre (LSC) | Sl. No. | Use Premise | Ma...
4. `MPD47_GAZETTE_EN:4.4.4:0` — clause 4.4.4, pages 767-767, [d22 b4 score 0.0156], zone_primary lda
   - path: 4.4 LOW DENSITY AREA (LDA) › 4.4.4 Other Controls:
   - 4.4.4 Other Controls: (i) For the purpose of subdivision of land which is above 10,000 sqm, an internal road of minimum width 12 meter may be planned ...
5. `MPD47_GAZETTE_EN:4.3.3@p758:0` — clause 4.3.3, pages 758-759, [b5 score 0.0154], zone_primary hdc
   - path: 4.3 HIGH DENSITY CORRIDOR DEVELOPMENT › 4.3.3 HDC Norms
   - 4.3.3 HDC Norms (i) Participation in the HDC Policy is voluntary. In case of HDC Plots, the land use shall be as per the sanctioned HDC project. Preva...

### hybrid

1. `MPD47_FAQ:Q5@p2:0` — clause Q5, pages 2-3, [d1 b1 score 0.0328]
   - path: FAQs - GENERIC › Q5. What provisions have been made for redevelopment under different land
   - Q5. What provisions have been made for redevelopment under different land uses? MPD-2047 allows redevelopment at the plot level with following provisi...
2. `MPD47_GAZETTE_EN:9.1.3:0` — clause 9.1.3, pages 837-837, [d9 b2 score 0.0306]
   - path: 9.1 Planned Industrial Area › 9.1.3 Permissible Uses for Use Conversion in Planned Industrial Areas
   - 9.1.3 Permissible Uses for Use Conversion in Planned Industrial Areas (i) Industrial units/plots shall be eligible for use conversion to Commercial Us...
3. `MPD47_GAZETTE_EN:4.5.3:0` — clause 4.5.3, pages 770-771, [d3 b8 score 0.0306]
   - path: 4.5 REGENERATION OF PLANNED AREAS › 4.5.3 Regeneration Area
   - 4.5.3 Regeneration Area (i) Conditions: (a) Minimum Plot area for undertaking regeneration shall be 3,000 sqm for Residential and 1,000 sqm for Commer...
4. `MPD47_GAZETTE_EN:8.1.2@p823:0` — clause 8.1.2, pages 823-824, [d13 b3 score 0.0296]
   - path: 8.1 General Business and Commerce › 8.1.2 Development Control Norms (DCN)
   - 8.1.2 Development Control Norms (DCN) (i) Convenience Shopping Centre (CSC) and Local Shopping Centre (LSC): Centre (LSC) | Sl. No. | Use Premise | Ma...
5. `MPD47_FAQ:Q3@p11:0` — clause Q3, pages 11-11, [d12 b6 score 0.0290], zone_primary tod
   - path: FAQs - Transit Oriented Development (TOD) Policy › Q3. What is the eligibility criteria?
   - Q3. What is the eligibility criteria? i. Minimum plot area of 2000 sqm. accessible from an existing road having a minimum ROW of 18m or proposed conti...

### hybrid+rerank

1. `MPD47_FAQ:Q5@p2:0` — clause Q5, pages 2-3, [d1 b1 rr1 rerank +9.31 score 0.0328]
   - path: FAQs - GENERIC › Q5. What provisions have been made for redevelopment under different land
   - Q5. What provisions have been made for redevelopment under different land uses? MPD-2047 allows redevelopment at the plot level with following provisi...
2. `MPD47_GAZETTE_EN:4.5.3:0` — clause 4.5.3, pages 770-771, [d3 b8 rr2 rerank +7.65 score 0.0306]
   - path: 4.5 REGENERATION OF PLANNED AREAS › 4.5.3 Regeneration Area
   - 4.5.3 Regeneration Area (i) Conditions: (a) Minimum Plot area for undertaking regeneration shall be 3,000 sqm for Residential and 1,000 sqm for Commer...
3. `MPD47_GAZETTE_EN:9.1.3:0` — clause 9.1.3, pages 837-837, [d9 b2 rr3 rerank +5.80 score 0.0306]
   - path: 9.1 Planned Industrial Area › 9.1.3 Permissible Uses for Use Conversion in Planned Industrial Areas
   - 9.1.3 Permissible Uses for Use Conversion in Planned Industrial Areas (i) Industrial units/plots shall be eligible for use conversion to Commercial Us...
4. `MPD47_FAQ:Q3@p11:0` — clause Q3, pages 11-11, [d12 b6 rr4 rerank +4.29 score 0.0290], zone_primary tod
   - path: FAQs - Transit Oriented Development (TOD) Policy › Q3. What is the eligibility criteria?
   - Q3. What is the eligibility criteria? i. Minimum plot area of 2000 sqm. accessible from an existing road having a minimum ROW of 18m or proposed conti...
5. `MPD47_GAZETTE_EN:13.2:0` — clause 13.2, pages 886-887, [d27 b15 rr5 rerank +4.22 score 0.0248]
   - path: 13.2 Norms for Data Centre
   - 13.2 Norms for Data Centre Data centre shall be permitted in Industrial, Commercial and PSP use zone with following norms: (i) Minimum plot area shall...

## 6. Does MPD-2047 replace MPD-2021?

### dense

1. `MPD47_FAQ:Q2@p2:0` — clause Q2, pages 2-2, [d1 b1 score 0.0164]
   - path: FAQs - GENERIC › Q2. Does the provisions of MPD-2047 supersede the MPD-2021?
   - Q2. Does the provisions of MPD-2047 supersede the MPD-2021? Yes, MPD-2047 supersedes the MPD-2021. However, any plan approved under earlier Master Pla...
2. `MPD47_FAQ:Q1@p2:0` — clause Q1, pages 2-2, [d2 b11 score 0.0161]
   - path: FAQs - GENERIC › Q1. Since when the MPD-2047 will be applicable?
   - Q1. Since when the MPD-2047 will be applicable? MPD-2047 is in force from the date of its notification in the Official Gazette, i.e., 20.08.2026.
3. `MPD47_FAQ:Q4@p2:0` — clause Q4, pages 2-2, [d3 b14 score 0.0159]
   - path: FAQs - GENERIC › Q4. Do all existing developments have to comply with the provisions of MPD-2047
   - Q4. Do all existing developments have to comply with the provisions of MPD-2047 immediately? Plans approved prior to notification of MPD-2047 shall co...
4. `MPD47_GAZETTE_EN:p647:0` — clause (none), pages 647-648, [d4 score 0.0156]
   - path: Notification preamble
   - The Master Plan for Delhi 2047 is aligned with the vision of Viksit Bharat @ 2047 and aims to transform Delhi into a world-class, inclusive, sustainab...
5. `MPD47_FAQ:Q7@p19:0` — clause Q7, pages 19-19, [d5 b26 score 0.0154], zone_primary lda
   - path: FAQs on LDA › Q7. What happens to existing sanctioned constructions on private land after
   - Q7. What happens to existing sanctioned constructions on private land after notification of the Plan? Existing sanctioned constructions on private lan...

### bm25

1. `MPD47_FAQ:Q2@p2:0` — clause Q2, pages 2-2, [d1 b1 score 0.0164]
   - path: FAQs - GENERIC › Q2. Does the provisions of MPD-2047 supersede the MPD-2021?
   - Q2. Does the provisions of MPD-2047 supersede the MPD-2021? Yes, MPD-2047 supersedes the MPD-2021. However, any plan approved under earlier Master Pla...
2. `MPD47_GAZETTE_EN:3.3@p1081:0` — clause 3.3, pages 1081-1081, [b2 score 0.0161]
   - path: 3. SERVICE PLAN – Delhi Cantonment Board (DCB) › 3.3 DETAILS OF MANAGEMENT OF PLASTIC WASTE
   - 3.3. DETAILS OF MANAGEMENT OF PLASTIC WASTE There is a complete ban on the use polythene bags of less than 50-micron thickness. The Assistant Sanitary...
3. `MPD47_GAZETTE_EN:1.4:0` — clause 1.4, pages 653-653, [b3 score 0.0159]
   - path: 1.4 Evolution of Master Plans (1962, 2001 and 2021)
   - 1.4 Evolution of Master Plans (1962, 2001 and 2021) The process of planned development of the National Capital began with enactment of the Delhi Devel...
4. `MPD47_GAZETTE_EN:1.5:0` — clause 1.5, pages 654-654, [b4 score 0.0156]
   - path: 1.5 Plan Preparation
   - 1.5 Plan Preparation In order to establish the present situation and assess gaps under various sectors, a baseline exercise was conducted for MPD, inv...
5. `MPD47_GAZETTE_EN:1.6.1@p655:0` — clause 1.6.1, pages 655-656, [b5 score 0.0154]
   - path: 1.6 Existing Scenario › 1.6.1 Demography
   - | Sl. No. | Year | Male (in million) | Female (in million) | Total (in million) | | --- | --- | --- | --- | --- | | 1. | 2021 | 11.1 | 9.5 | 20.6 | | ...

### hybrid

1. `MPD47_FAQ:Q2@p2:0` — clause Q2, pages 2-2, [d1 b1 score 0.0328]
   - path: FAQs - GENERIC › Q2. Does the provisions of MPD-2047 supersede the MPD-2021?
   - Q2. Does the provisions of MPD-2047 supersede the MPD-2021? Yes, MPD-2047 supersedes the MPD-2021. However, any plan approved under earlier Master Pla...
2. `MPD47_FAQ:Q1@p2:0` — clause Q1, pages 2-2, [d2 b11 score 0.0302]
   - path: FAQs - GENERIC › Q1. Since when the MPD-2047 will be applicable?
   - Q1. Since when the MPD-2047 will be applicable? MPD-2047 is in force from the date of its notification in the Official Gazette, i.e., 20.08.2026.
3. `MPD47_GAZETTE_EN:p640:0` — clause (none), pages 640-641, [d6 b8 score 0.0299]
   - path: Notification preamble
   - MINISTRY OF HOUSING AND URBAN AFFAIRS (Department of Capital Development) (DELHI DIVISION) NOTIFICATION New Delhi, the 20th August, 2026 S.O. 4597(E)....
4. `MPD47_FAQ:Q4@p2:0` — clause Q4, pages 2-2, [d3 b14 score 0.0294]
   - path: FAQs - GENERIC › Q4. Do all existing developments have to comply with the provisions of MPD-2047
   - Q4. Do all existing developments have to comply with the provisions of MPD-2047 immediately? Plans approved prior to notification of MPD-2047 shall co...
5. `MPD47_FAQ:Q2@p18:0` — clause Q2, pages 18-18, [d10 b16 score 0.0274], zone_primary lda
   - path: FAQs on LDA › Q2. Where do LDA provisions NOT apply?
   - Q2. Where do LDA provisions NOT apply? The areas where the provisions of the LDA shall not be applicable are listed under Clause 4.1 (ii) of MPD-2047.

### hybrid+rerank

1. `MPD47_FAQ:Q2@p2:0` — clause Q2, pages 2-2, [d1 b1 rr1 rerank +10.08 score 0.0328]
   - path: FAQs - GENERIC › Q2. Does the provisions of MPD-2047 supersede the MPD-2021?
   - Q2. Does the provisions of MPD-2047 supersede the MPD-2021? Yes, MPD-2047 supersedes the MPD-2021. However, any plan approved under earlier Master Pla...
2. `MPD47_FAQ:Q1@p2:0` — clause Q1, pages 2-2, [d2 b11 rr2 rerank +5.79 score 0.0302]
   - path: FAQs - GENERIC › Q1. Since when the MPD-2047 will be applicable?
   - Q1. Since when the MPD-2047 will be applicable? MPD-2047 is in force from the date of its notification in the Official Gazette, i.e., 20.08.2026.
3. `MPD47_FAQ:Q4@p2:0` — clause Q4, pages 2-2, [d3 b14 rr3 rerank +4.61 score 0.0294]
   - path: FAQs - GENERIC › Q4. Do all existing developments have to comply with the provisions of MPD-2047
   - Q4. Do all existing developments have to comply with the provisions of MPD-2047 immediately? Plans approved prior to notification of MPD-2047 shall co...
4. `MPD47_GAZETTE_EN:p647:0` — clause (none), pages 647-648, [d4 rr4 rerank +3.65 score 0.0156]
   - path: Notification preamble
   - The Master Plan for Delhi 2047 is aligned with the vision of Viksit Bharat @ 2047 and aims to transform Delhi into a world-class, inclusive, sustainab...
5. `MPD47_GAZETTE_EN:p646:0` — clause (none), pages 646-647, [b7 rr5 rerank +2.80 score 0.0149]
   - path: Notification preamble
   - 23. The collaborative governance framework under MPD–2047 promotes coordinated planning, decision-making and implementation through the active partici...

## 7. Where can I find the permissible activities for a use premise?

### dense

1. `MPD47_GAZETTE_EN:Annexure 21@p970:0` — clause Annexure 21, pages 970-970, [d1 b7 score 0.0164]
   - path: Annexure 21: Use Premises and Permissible Activities
   - 5. Industry: | S. No. | Use Premise | | Activities Permitted | | --- | --- | --- | --- | | 1. | Industrial Plotted | Up to 400 sqm | Permissible indus...
2. `MPD47_FAQ:Q7@p3:0` — clause Q7, pages 3-3, [d2 b4 score 0.0161]
   - path: FAQs - GENERIC › Q7. What are the permissible activities in different use zones?
   - Q7. What are the permissible activities in different use zones? Permitted and non-permitted Use Premises/activities for each use zone are listed as: •...
3. `MPD47_GAZETTE_EN:Annexure 21@p972:0` — clause Annexure 21, pages 972-972, [d3 score 0.0159]
   - path: Annexure 21: Use Premises and Permissible Activities
   - | S. No. | Use Premise | Activities Permitted | | --- | --- | --- | | | | Open Air Theatre/ Amphitheatre, Aquarium, Playground, Play area/ Children Pa...
4. `MPD47_GAZETTE_EN:Annexure 21@p967:0` — clause Annexure 21, pages 967-967, [d4 score 0.0156]
   - path: Annexure 21: Use Premises and Permissible Activities
   - 2. Commercial: | S. No. | Use Premise | Activities Permitted | | --- | --- | --- | | 1. | Convenience Shopping Centre (CSC) | Retail Shop, Vending Boo...
5. `MPD47_GAZETTE_EN:Annexure 21@p976:0` — clause Annexure 21, pages 976-976, [d5 b21 score 0.0154]
   - path: Annexure 21: Use Premises and Permissible Activities
   - | S. No. | Use Premise | Activities Permitted | | --- | --- | --- | | | | booth/ kiosk, Accommodation for Staff, Patient attendant accommodation, Host...

### bm25

1. `MPD47_GAZETTE_EN:8.2.1:0` — clause 8.2.1, pages 828-828, [b1 score 0.0164]
   - path: 8.2 IFC, Wholesale Market, Warehousing scheme › 8.2.1 Use Premise, Definitions and Permissible Activities
   - 8.2 IFC, Wholesale Market, Warehousing scheme 8.2.1 Use Premise, Definitions and Permissible Activities and Permissible Activities | Sl. No. | Use Pre...
2. `MPD47_FAQ:Q3@p2:0` — clause Q3, pages 2-2, [d8 b2 score 0.0161]
   - path: FAQs - GENERIC › Q3. How can I know the land use, Use Premise and permitted Activity for my
   - Q3. How can I know the land use, Use Premise and permitted Activity for my property? Land use for referral purpose can be ascertained from the GIS-bas...
3. `MPD47_GAZETTE_EN:8.3.1:0` — clause 8.3.1, pages 830-830, [d29 b3 score 0.0159]
   - path: 8.3 Hotel › 8.3.1 Use Premises, Definitions and Permissible Activities
   - 8.3 Hotel 8.3.1 Use Premises, Definitions and Permissible Activities | Sl. No. | Use Premise | Definition | | --- | --- | --- | | 1. | Hotel | An esta...
4. `MPD47_FAQ:Q7@p3:0` — clause Q7, pages 3-3, [d2 b4 score 0.0156]
   - path: FAQs - GENERIC › Q7. What are the permissible activities in different use zones?
   - Q7. What are the permissible activities in different use zones? Permitted and non-permitted Use Premises/activities for each use zone are listed as: •...
5. `MPD47_GAZETTE_EN:5.1.5:0` — clause 5.1.5, pages 798-799, [d10 b5 score 0.0154]
   - path: 5.1 Development Code › 5.1.5 Designated Use Zones and Use Premises
   - 5.1.5 Designated Use Zones and Use Premises (i) Each Use Zone comprises of distinct Use Premises (Annexure 22). The Use Premises further comprise of c...

### hybrid

1. `MPD47_FAQ:Q7@p3:0` — clause Q7, pages 3-3, [d2 b4 score 0.0318]
   - path: FAQs - GENERIC › Q7. What are the permissible activities in different use zones?
   - Q7. What are the permissible activities in different use zones? Permitted and non-permitted Use Premises/activities for each use zone are listed as: •...
2. `MPD47_GAZETTE_EN:Annexure 21@p970:0` — clause Annexure 21, pages 970-970, [d1 b7 score 0.0313]
   - path: Annexure 21: Use Premises and Permissible Activities
   - 5. Industry: | S. No. | Use Premise | | Activities Permitted | | --- | --- | --- | --- | | 1. | Industrial Plotted | Up to 400 sqm | Permissible indus...
3. `MPD47_FAQ:Q3@p2:0` — clause Q3, pages 2-2, [d8 b2 score 0.0308]
   - path: FAQs - GENERIC › Q3. How can I know the land use, Use Premise and permitted Activity for my
   - Q3. How can I know the land use, Use Premise and permitted Activity for my property? Land use for referral purpose can be ascertained from the GIS-bas...
4. `MPD47_GAZETTE_EN:5.1.5:0` — clause 5.1.5, pages 798-799, [d10 b5 score 0.0297]
   - path: 5.1 Development Code › 5.1.5 Designated Use Zones and Use Premises
   - 5.1.5 Designated Use Zones and Use Premises (i) Each Use Zone comprises of distinct Use Premises (Annexure 22). The Use Premises further comprise of c...
5. `MPD47_GAZETTE_EN:Annexure 21@p966:0` — clause Annexure 21, pages 966-967, [d7 b10 score 0.0292]
   - path: Annexure 21: Use Premises and Permissible Activities
   - Annexure 21: Use Premises and Permissible Activities 1. Residential: | S. No. | Use Premise | Activities Permitted | | --- | --- | --- | | 1. | Group ...

### hybrid+rerank

1. `MPD47_FAQ:Q3@p2:0` — clause Q3, pages 2-2, [d8 b2 rr1 rerank +6.17 score 0.0308]
   - path: FAQs - GENERIC › Q3. How can I know the land use, Use Premise and permitted Activity for my
   - Q3. How can I know the land use, Use Premise and permitted Activity for my property? Land use for referral purpose can be ascertained from the GIS-bas...
2. `MPD47_FAQ:Q7@p3:0` — clause Q7, pages 3-3, [d2 b4 rr2 rerank +5.39 score 0.0318]
   - path: FAQs - GENERIC › Q7. What are the permissible activities in different use zones?
   - Q7. What are the permissible activities in different use zones? Permitted and non-permitted Use Premises/activities for each use zone are listed as: •...
3. `MPD47_GAZETTE_EN:8.2.1:0` — clause 8.2.1, pages 828-828, [b1 rr3 rerank +4.34 score 0.0164]
   - path: 8.2 IFC, Wholesale Market, Warehousing scheme › 8.2.1 Use Premise, Definitions and Permissible Activities
   - 8.2 IFC, Wholesale Market, Warehousing scheme 8.2.1 Use Premise, Definitions and Permissible Activities and Permissible Activities | Sl. No. | Use Pre...
4. `MPD47_GAZETTE_EN:Annexure 21@p966:0` — clause Annexure 21, pages 966-967, [d7 b10 rr4 rerank +3.67 score 0.0292]
   - path: Annexure 21: Use Premises and Permissible Activities
   - Annexure 21: Use Premises and Permissible Activities 1. Residential: | S. No. | Use Premise | Activities Permitted | | --- | --- | --- | | 1. | Group ...
5. `MPD47_GAZETTE_EN:5.1.5:0` — clause 5.1.5, pages 798-799, [d10 b5 rr5 rerank +3.60 score 0.0297]
   - path: 5.1 Development Code › 5.1.5 Designated Use Zones and Use Premises
   - 5.1.5 Designated Use Zones and Use Premises (i) Each Use Zone comprises of distinct Use Premises (Annexure 22). The Use Premises further comprise of c...

## 8. What is the land pooling policy and which zones does it cover?

### dense

1. `MPD47_FAQ:Q3@p8:0` — clause Q3, pages 8-8, [d1 b1 score 0.0164], zone_primary land_pooling
   - path: FAQs – Land Pooling Policy › Q3. Which areas will come under land pooling policy?
   - Q3. Which areas will come under land pooling policy? This policy is applicable in the areas of Planning Zones K-I, L, N, P-II, J (part) and part of P-...
2. `MPD47_FAQ:Q6@p8:0` — clause Q6, pages 8-8, [d2 b2 score 0.0161], zone_primary land_pooling
   - path: FAQs – Land Pooling Policy › Q6. What are the areas excluded under land pooling policy?
   - Q6. What are the areas excluded under land pooling policy? Land Pooling Policy is applicable in areas of Planning Zones K-I, L, N, P-II, J (part) and ...
3. `MPD47_FAQ:Q1@p8:0` — clause Q1, pages 8-8, [d3 b7 score 0.0159], zone_primary land_pooling
   - path: FAQs – Land Pooling Policy › Q1. What is Land Pooling Policy of Delhi?
   - Q1. What is Land Pooling Policy of Delhi? Land Pooling Policy is a new framework for urban development, wherein the private entity/ landowners will pl...
4. `MPD47_GAZETTE_EN:4.1@p746:0` — clause 4.1, pages 746-746, [d4 b13 score 0.0156], zone_primary land_pooling
   - path: 4.1 LAND POOLING
   - 4.1 LAND POOLING Land Pooling Policy is a new framework for urban development, wherein the private entity/ landowners will play an active role in deve...
5. `MPD47_FAQ:Q4@p8:0` — clause Q4, pages 8-8, [d5 b8 score 0.0154], zone_primary land_pooling
   - path: FAQs – Land Pooling Policy › Q4. Who can participate in Land Pooling Policy?
   - Q4. Who can participate in Land Pooling Policy? Landowners with any size of land parcel falling in land pooling areas can register and participate as ...

### bm25

1. `MPD47_FAQ:Q3@p8:0` — clause Q3, pages 8-8, [d1 b1 score 0.0164], zone_primary land_pooling
   - path: FAQs – Land Pooling Policy › Q3. Which areas will come under land pooling policy?
   - Q3. Which areas will come under land pooling policy? This policy is applicable in the areas of Planning Zones K-I, L, N, P-II, J (part) and part of P-...
2. `MPD47_FAQ:Q6@p8:0` — clause Q6, pages 8-8, [d2 b2 score 0.0161], zone_primary land_pooling
   - path: FAQs – Land Pooling Policy › Q6. What are the areas excluded under land pooling policy?
   - Q6. What are the areas excluded under land pooling policy? Land Pooling Policy is applicable in areas of Planning Zones K-I, L, N, P-II, J (part) and ...
3. `MPD47_FAQ:Q18@p10:0` — clause Q18, pages 10-10, [d9 b3 score 0.0159], zone_primary land_pooling
   - path: FAQs – Land Pooling Policy › Q18. I have built-up structure on my land for which the plan is approved /
   - Q18. I have built-up structure on my land for which the plan is approved / sanctioned by the Govt. agencies. If I do not participate in land pooling w...
4. `MPD47_GAZETTE_EN:4.1.2:0` — clause 4.1.2, pages 747-748, [d8 b4 score 0.0156], zone_primary land_pooling
   - path: 4.1 LAND POOLING › 4.1.2 Guiding Principles
   - 4.1.2 Guiding Principles (i) Preparation of schemes in the land pooling areas shall be taken up by adopting any of the following development models: (...
5. `MPD47_FAQ:Q5@p8:0` — clause Q5, pages 8-8, [d7 b5 score 0.0154], zone_primary land_pooling
   - path: FAQs – Land Pooling Policy › Q5. What is the minimum land size to participate in Land Pooling?
   - Q5. What is the minimum land size to participate in Land Pooling? Land parcels of any size can be brought under pooling, provided they fall in the are...

### hybrid

1. `MPD47_FAQ:Q3@p8:0` — clause Q3, pages 8-8, [d1 b1 score 0.0328], zone_primary land_pooling
   - path: FAQs – Land Pooling Policy › Q3. Which areas will come under land pooling policy?
   - Q3. Which areas will come under land pooling policy? This policy is applicable in the areas of Planning Zones K-I, L, N, P-II, J (part) and part of P-...
2. `MPD47_FAQ:Q6@p8:0` — clause Q6, pages 8-8, [d2 b2 score 0.0323], zone_primary land_pooling
   - path: FAQs – Land Pooling Policy › Q6. What are the areas excluded under land pooling policy?
   - Q6. What are the areas excluded under land pooling policy? Land Pooling Policy is applicable in areas of Planning Zones K-I, L, N, P-II, J (part) and ...
3. `MPD47_FAQ:Q1@p8:0` — clause Q1, pages 8-8, [d3 b7 score 0.0308], zone_primary land_pooling
   - path: FAQs – Land Pooling Policy › Q1. What is Land Pooling Policy of Delhi?
   - Q1. What is Land Pooling Policy of Delhi? Land Pooling Policy is a new framework for urban development, wherein the private entity/ landowners will pl...
4. `MPD47_FAQ:Q18@p10:0` — clause Q18, pages 10-10, [d9 b3 score 0.0304], zone_primary land_pooling
   - path: FAQs – Land Pooling Policy › Q18. I have built-up structure on my land for which the plan is approved /
   - Q18. I have built-up structure on my land for which the plan is approved / sanctioned by the Govt. agencies. If I do not participate in land pooling w...
5. `MPD47_GAZETTE_EN:4.1.2:0` — clause 4.1.2, pages 747-748, [d8 b4 score 0.0303], zone_primary land_pooling
   - path: 4.1 LAND POOLING › 4.1.2 Guiding Principles
   - 4.1.2 Guiding Principles (i) Preparation of schemes in the land pooling areas shall be taken up by adopting any of the following development models: (...

### hybrid+rerank

1. `MPD47_FAQ:Q6@p8:0` — clause Q6, pages 8-8, [d2 b2 rr1 rerank +7.11 score 0.0323], zone_primary land_pooling
   - path: FAQs – Land Pooling Policy › Q6. What are the areas excluded under land pooling policy?
   - Q6. What are the areas excluded under land pooling policy? Land Pooling Policy is applicable in areas of Planning Zones K-I, L, N, P-II, J (part) and ...
2. `MPD47_FAQ:Q3@p8:0` — clause Q3, pages 8-8, [d1 b1 rr2 rerank +7.03 score 0.0328], zone_primary land_pooling
   - path: FAQs – Land Pooling Policy › Q3. Which areas will come under land pooling policy?
   - Q3. Which areas will come under land pooling policy? This policy is applicable in the areas of Planning Zones K-I, L, N, P-II, J (part) and part of P-...
3. `MPD47_FAQ:Q1@p8:0` — clause Q1, pages 8-8, [d3 b7 rr3 rerank +4.13 score 0.0308], zone_primary land_pooling
   - path: FAQs – Land Pooling Policy › Q1. What is Land Pooling Policy of Delhi?
   - Q1. What is Land Pooling Policy of Delhi? Land Pooling Policy is a new framework for urban development, wherein the private entity/ landowners will pl...
4. `MPD47_GAZETTE_EN:4.1@p746:0` — clause 4.1, pages 746-746, [d4 b13 rr4 rerank +3.32 score 0.0293], zone_primary land_pooling
   - path: 4.1 LAND POOLING
   - 4.1 LAND POOLING Land Pooling Policy is a new framework for urban development, wherein the private entity/ landowners will play an active role in deve...
5. `MPD47_GAZETTE_EN:1.7.1@p665:1` — clause 1.7.1, pages 665-666, [d12 b17 rr5 rerank +2.28 score 0.0269]
   - path: 1.7 Land Use Plan for NCT of Delhi › 1.7.1 Land Use Plan
   - (ii) Policy Led Development Areas: These comprise areas where development shall be through participatory planning mechanisms involving private landown...
