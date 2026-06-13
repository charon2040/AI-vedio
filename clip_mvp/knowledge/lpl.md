# LPL 项目知识库

用途：给 LLM 提供 LPL 赛事剪辑中的长期实体、别名和术语背景，减少选手、队伍、术语错乱。

边界：
- 这里只放长期或项目级可复用信息。
- 不在知识库里写“本局谁在左边/右边”“本局谁选了什么英雄”“本局谁赢了哪波团”等单场事实。
- 单场事实必须放在任务的“本次补充事实”里，或由原始字幕证明。
- 如果字幕和本次补充事实冲突，以本次补充事实优先；如果都不明确，文案应保持中性，不要靠模型记忆补全。

赛事与队伍：
- LPL = League of Legends Pro League，中国大陆《英雄联盟》职业联赛。
- AL = Anyone's Legend，中文常写作 AL、AL 战队。
- WBG = Weibo Gaming，中文常写作 WBG、微博、微博战队。

2026 LPL 队伍与选手归属：
- AL / Anyone's Legend / AL 战队：Top Flandre（圣枪哥）；Jungle Tarzan；Mid Shanks（香克斯）；ADC Hope；Support Kael（卡尔）。
- BLG / Bilibili Gaming / 哔哩哔哩：Top Bin；Jungle Xun；Mid Knight；ADC Viper；Support ON。
- EDG / EDward Gaming：Top Zdz；Jungle Xiaohao；Mid Angel；ADC Leave；Support Parukia。
- IG / Invictus Gaming / iG：Top Soboro；Jungle Wei；Mid Rookie / Renard；ADC Photic；Support Meiko / Jwei。
- JDG / JD Gaming / 京东：Top Xiaoxu；Jungle Junjia；Mid HongQ；ADC GALA；Support Vampire。
- LGD / LGD Gaming：Top sasi；Jungle Heng；Mid Tangyuan；ADC Shaoye；Support ycx。
- LNG / LNG Esports：Top sheer；Jungle Croco；Mid BullDoG；ADC 1xn；Support Missing。
- NIP / Ninjas in Pyjamas：Top HOYA / Alley；Jungle Guwon；Mid Care；ADC Assum；Support zhuo。
- OMG / Oh My God：Top Hery；Jungle re0 / Juhan；Mid haichao；ADC Starry；Support Moham。
- TES / Top Esports / 滔搏：Top 369；Jungle naiyou；Mid Creme；ADC JackeyLove / JiaQi；Support Hang / fengyu。
- TT / ThunderTalk Gaming：Top Keshi；Jungle Junhao；Mid xlun / Heru；ADC Ryan3；Support Feather。
- UP / Ultra Prime：Top Liangchen；Jungle Grizzly；Mid Saber；ADC Hena；Support Xiaoxia。
- WBG / Weibo Gaming / 微博：Top Zika（紫卡） / Breathe；Jungle Jiejie（杰杰）；Mid Xiaohu（小虎）；ADC Elk；Support Erha（二哈） / Crisp。
- WE / Team WE：Top Cube；Jungle Monki；Mid Karis；ADC About；Support yaoyao。

常见中文名 / ID 速查：
- Flandre = 圣枪哥。
- Shanks = 香克斯。
- Kael = 卡尔。
- Zika = 紫卡。
- Jiejie = 杰杰。
- Xiaohu = 小虎。
- TES = 滔搏。
- WBG = 微博。
- BLG = 哔哩哔哩。
- JDG = 京东。

常用术语：
- BP = Ban/Pick，赛前禁用与选择英雄阶段。
- 蓝色方 / 红色方 = 本局对战双方的阵营方位，是单场事实，不能只靠知识库判断。
- 上路 / 打野 / 中路 / 下路 / 辅助 = TOP / JUNGLE / MID / ADC / SUPPORT。
- 双 C = 中单与 ADC，通常指主要输出核心。
- 小龙 = 元素亚龙；龙魂 = 一方累计四条元素龙后的团队增益。
- 电龙魂 = 海克斯科技龙魂相关增益，口播可能说成电龙、闪电链、减速、拉扯。
- 大龙 = 纳什男爵；远古龙 = Elder Dragon；三龙会通常指同时拥有大龙、龙魂、远古龙等强资源组合。
- 先锋 / 巢虫 / 虫子 = 前期地图资源，字幕可能混用。
- 开团 = 主动发起团战；反手 = 等对方先进场后再控制和反打。
- 单带 = 一名英雄在边路持续推进和牵制。
- Poke = 远程消耗。
- 排眼 / 做视野 / 卡视野 = 视野控制相关动作。

写稿原则：
- 队伍归属、阵营方位、英雄归属、击杀和资源归属属于单场事实，必须来自本次补充事实或原始字幕。
- 知识库里的选手常见位置只能帮助理解“这个名字是谁”，不能单独证明他本局使用了哪个英雄。
- 选手归属会随转会期变化；如果用户提供了本次项目名单，以用户提供的名单为准。
- 如果字幕只是在讨论某个英雄池、历史招牌或可能选择，不能写成“本局已经选用”。
- 如果字幕 ASR 把名字识别错，例如 Kael/卡尔、Erha/二哈、Xiaohu/小虎，应结合上下文和本次补充事实判断。
