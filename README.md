## データ出典

国土交通省 道路局が公表する[令和3年度 全国道路・街路交通情勢調査（道路交通センサス）一般交通量調査](https://www.mlit.go.jp/road/census/r3/)です。

- 箇所別基本表:
  交通調査基本区間ごとの交通量・混雑度・旅行速度・道路構造・沿道状況を収録した都道府県別の CSV です。
- 時間帯別交通量表:
  交通量調査単位区間・上下・車種ごとに、7時台から翌6時台までの1時間ごとの交通量を収録した都道府県別の CSV です。
- [一般交通量調査結果の可視化ツール](https://www.mlit.go.jp/road/ir/ir-data/census_visualizationR3/index.html):
  区間の形状を道路種別ごとの GeoJSON タイル（z12）で配信しています。区間番号で箇所別基本表と結び付けます。

対象は高速自動車国道・都市高速道路・一般国道・主要地方道（都道府県道・指定市市道）・一般都道府県道・
指定市の一般市道の7区分で、一般市町村道は調査の対象外です。

あわせて、国土交通省 不動産・建設経済局が毎月公表する[不動産価格指数](https://www.mlit.go.jp/totikensangyo/totikensangyo_tk5_000085.html)の
「最新データ」にある Excel を取り込みます。

- 不動産価格指数（住宅）:
  全国・地方ブロック・都市圏・東京都・愛知県・大阪府の月次の指数です。1シートが1地域で、季節調整値と原系列をシートで分けています。
- 不動産価格指数（商業用不動産）:
  全国・三大都市圏・三大都市圏以外の地域・南関東圏の四半期の指数です。シートの分け方は住宅と同じです。

さらに、国土交通省 総合政策局 建設経済統計調査室が毎月公表する[建設工事費デフレーター](https://www.mlit.go.jp/statistics/details/t-other-2_tk_000362.html)の
統計表の Excel を取り込みます。

- 月次:
  2016年4月からの月別の指数です。過去の月は Excel 上で行が非表示になっているだけで、シートの中にあります。
- 年度次:
  1951年度からの年度別の指数です。公表されていない工事種類・年度は「***」になっています。

あわせて、農林水産省と国土交通省が毎年決める[公共工事設計労務単価](https://www.mlit.go.jp/totikensangyo/const/1_6_bt_000217.html)を、
改定ごとの記者発表の PDF にある単価表から取り込みます。単価表は1ページに10職種 × 47都道府県で、5ページあります。
同じ PDF の後ろにある、必要経費を含めた金額を併記した参考公表の表は取り込みません。

## スキーマ: road

### テーブル: traffic_census_section

交通調査基本区間ごとの結果です。1行 = 1区間で、全国の99,417区間を収録します。

- survey_year: 調査年度（INTEGER、令和3年度調査は 2021）
- section_id: 交通調査基本区間番号（VARCHAR、11桁。この表で一意）
- generation_code: 世代管理番号（VARCHAR、区間の分割・属性変更で繰り上がる）
- prefecture_code: 都道府県コード（VARCHAR、2桁）
- road_type_code / road_type: 道路種別（INTEGER / VARCHAR、1=高速自動車国道〜7=指定市の一般市道）
- route_number / route_name: 路線番号・路線名（VARCHAR）
- administrator_code / administrator: 管理区分・道路管理者（INTEGER / VARCHAR）
- city_code: 市区町村コード（VARCHAR、5桁。令和3年4月1日時点の標準コードで、指定市は区ごと）
- is_motorway: 自動車専用道路か（BOOLEAN）
- section_type_code / section_type: 区間種別（INTEGER / VARCHAR、通常区間・上下線分離区間・複断面区間など）
- section_length_km: 区間延長（DOUBLE、km）
- oneway_code: 一方通行フラグ（INTEGER、0=なし、1=起点から終点方向、2=終点から起点方向）
- section_id_h27: 平成27年度の交通調査基本区間番号（VARCHAR、11桁。年度をまたぐ突合に使う）
- traffic_pref_city_code / traffic_survey_unit_id: 交通量調査の都道府県指定市コード・調査単位区間番号（VARCHAR、traffic_census_hourly への結合キー）
- up_observation_point / down_observation_point: 上り・下りの交通量観測地点地名（VARCHAR）
- up_observation_code / down_observation_code: 上り・下りの観測・非観測コード（INTEGER）
- up_observation_type / down_observation_type: 上り・下りの観測・非観測の別（VARCHAR、観測／非観測（推定値）／データなし（推定不能））
- up_observation_date / down_observation_date: 上り・下りの交通量観測年月日（INTEGER、YYYYMMDD。機械観測で複数日を使った場合は日が 00）
- up_volume_12h / down_volume_12h: 上り・下りの昼間12時間交通量（INTEGER、台。午前7時〜午後7時）
- up_volume_24h / down_volume_24h: 上り・下りの24時間交通量（INTEGER、台）
- volume_12h_small / volume_12h_large / volume_12h: 昼間12時間交通量の小型車・大型車・合計（INTEGER、台、上下合計）
- volume_24h_small / volume_24h_large / volume_24h: 24時間交通量の小型車・大型車・合計（INTEGER、台、上下合計）
- day_night_ratio: 昼夜率（DOUBLE、24時間交通量 ÷ 昼間12時間交通量）
- peak_ratio_12h: 昼間12時間ピーク比率（DOUBLE、%）
- large_vehicle_ratio_12h: 昼間12時間大型車混入率（DOUBLE、%）
- congestion_degree: 混雑度（DOUBLE、交通量 ÷ 交通容量。1.0 を超えると需要が容量を上回る）
- volume_12h_h27 / volume_24h_h27: 平成27年度の昼間12時間・24時間交通量（INTEGER、台）
- speed_peak_up / speed_peak_down: 朝夕（混雑時）の旅行速度 上り・下り（DOUBLE、km/h）
- speed_offpeak_up / speed_offpeak_down: 昼間（非混雑時）の旅行速度 上り・下り（DOUBLE、km/h）
- speed_12h_up / speed_12h_down: 昼間12時間平均旅行速度 上り・下り（DOUBLE、km/h、時間帯別交通量で加重）
- road_width_m: 道路部幅員（DOUBLE、m）
- carriageway_width_m: 車道幅員（DOUBLE、m）
- lanes: 車線数（INTEGER）
- sidewalk_ratio: 歩道設置率（DOUBLE、%）
- bus_route_ratio: バス路線延長率（DOUBLE、%）
- signalized_intersection_density / unsignalized_intersection_density: 信号交差点・信号のない交差点の密度（DOUBLE、箇所/km）
- green_time_ratio: 代表信号交差点の青時間比（DOUBLE、%）
- speed_limit: 指定最高速度（INTEGER、km/h）
- roadside_type_code / roadside_type: 代表沿道状況（INTEGER / VARCHAR、人口集中地区かつ商業地域／人口集中地区（商業地域を除く）／その他市街部／平地部／山地部）
- geometry: 区間形状（GEOMETRY、MultiLineString）

交通量は全区間が実測ではありません。observation_type が「非観測（推定値）」の区間は、平成27年度調査の
交通量と両年度で観測した区間のデータから推定した値です。「データなし（推定不能）」の区間は交通量が NULL です。

区間形状は、可視化ツールが配信するタイルを区間番号でまとめたものです。タイルは境界で区間を切るので、
同じ区間の線分を集めて1つの MultiLineString にしています。配信時に座標が小数5桁（約1m）に丸められているため、
原典の精度そのものではありません。形状が得られなかった区間は geometry が NULL で、99,417区間中350区間（0.35%）です。

配布 CSV は北海道〜茨城（都道府県コード01〜09）でコード類の先頭の0が落ちているため、区間番号は11桁、
市区町村コードと都道府県指定市コードは5桁に揃えています。

### テーブル: traffic_census_hourly

時間帯別交通量です。1行 = 交通量調査単位区間 × 上下 × 車種 × 時間帯で、7時台から翌6時台までの24時間分を縦持ちにしています。

- survey_year: 調査年度（INTEGER、令和3年度調査は 2021）
- prefecture_code: 都道府県コード（VARCHAR、2桁）
- pref_city_code: 都道府県指定市コード（VARCHAR、5桁）
- survey_unit_id: 交通量調査単位区間番号（VARCHAR）
- road_type_code: 道路種別コード（INTEGER）
- route_number: 路線番号（VARCHAR）
- observation_code / observation_type: 観測・非観測の別（INTEGER / VARCHAR、観測／非観測（推定値）／データなし（推定不能））
- observation_hours_code: 12時間・24時間観測の別（INTEGER、1=12時間観測地点、2=24時間観測地点。非観測で個別調査の観測値も使っていない区間は NULL）
- observation_date: 交通量観測年月日（INTEGER、YYYYMMDD。非観測でも個別調査の観測値を使った区間はその調査の日付を持ち、令和3年度より前のことがある。日付の無い区間は NULL）
- weather: 天候（VARCHAR、晴／曇／雨／霧／雪／不明。機械観測は不明）
- direction: 上り・下りの別（VARCHAR）
- vehicle_type: 車種区分（VARCHAR、小型車／大型車）
- hour: 時間帯（INTEGER、0〜23。その時刻台の1時間）
- hour_order: 観測順（INTEGER、7時台を0とした0〜23）
- is_daytime_12h: 昼間12時間に含まれるか（BOOLEAN、7時台〜18時台が true）
- volume: 時間帯別自動車類交通量（INTEGER、台/時）

区間の単位は交通調査基本区間ではなく、それを集約した交通量調査単位区間です。traffic_census_section とは
(traffic_pref_city_code, traffic_survey_unit_id) = (pref_city_code, survey_unit_id) で結合できますが、
1つの観測値が複数の基本区間に付くので、基本区間をまたいで合計すると二重に数えます。
調査の1日は7時台に始まり翌6時台に終わるため、時刻順の並べ替えには hour_order を使ってください。

## スキーマ: real_estate

### テーブル: price_index_residential

不動産価格指数（住宅）です。1行 = 地域 × 季節調整の別 × 用途 × 月で、2008年4月から収録します。

- region_code: 地域番号（VARCHAR、1=全国、2-1〜2-9=地方ブロック、3-1〜3-3=都市圏、4-1〜4-3=都府県）
- region_name: 地域名（VARCHAR）
- prefecture_code: 都道府県コード（VARCHAR、2桁。東京都・愛知県・大阪府の行だけに入る）
- adjustment: 季節調整の別（VARCHAR、季節調整／原系列）
- category: 用途（VARCHAR、住宅総合／住宅地／戸建住宅／マンション(区分所有)）
- period_start: 対象月（DATE、その月の1日）
- year / month: 年・月（INTEGER）
- price_index: 不動産価格指数（DOUBLE、2010年平均 = 100）
- change_basis: 変化率の比べ方（VARCHAR、季節調整値は対前月比、原系列は対前年同月比）
- change_rate: 変化率（DOUBLE、%）
- sample_count: サンプル数（INTEGER、指数の算出に使った取引の件数）

地域は上位と下位が同じ表に並ぶので、合計や平均を取るときは地域の階層をまたがないように絞ってください。

### テーブル: price_index_commercial

不動産価格指数（商業用不動産）です。1行 = 地域 × 季節調整の別 × 用途 × 四半期で、2008年第2四半期から収録します。

- region_code: 地域番号（VARCHAR、1=全国、2-1=三大都市圏、2-2=三大都市圏以外の地域、2-3=南関東圏。住宅の表の地域番号とは対応しない）
- region_name: 地域名（VARCHAR）
- adjustment: 季節調整の別（VARCHAR、季節調整／原系列）
- category: 用途（VARCHAR、商業用不動産総合／建物付土地総合／店舗／オフィス／倉庫／工場／マンション・アパート(一棟)／土地総合／商業地／工業地）
- period_start: 対象四半期の初日（DATE）
- year / quarter: 年・四半期（INTEGER、第1四半期 = 1〜3月）
- price_index: 不動産価格指数（DOUBLE、2010年平均 = 100）
- change_basis: 変化率の比べ方（VARCHAR、季節調整値は対前期比、原系列は対前年同期比）
- change_rate: 変化率（DOUBLE、%）
- sample_count: サンプル数（INTEGER）

南関東圏は倉庫・工場を公表しておらず、商業用不動産総合・建物付土地総合も無いため、6用途だけを持ちます。

取り込むのは国土交通省が集計する2008年4月（商業用は2008年第2四半期）以降です。住宅の都府県シートにある2008年3月以前の系列と、
商業用の都府県シート（1984年からの年次）は、国土交通省のほかに各都府県の不動産鑑定士協会を出典として明示するよう注記がある系列なので取り込んでいません。

## スキーマ: construction

### テーブル: cost_deflator_monthly

建設工事費デフレーター（月次）です。1行 = 工事種類 × 月で、2016年4月から収録します。
建設工事の名目の工事費を2020年度価格の実質額に直す指数で、名目額をこの指数で割って100を掛けると実質額になります。

- category_order: 工事種類の並び順（INTEGER、公表資料の列の順で1〜75）
- category: 工事種類（VARCHAR、公表資料の見出しの名前。住宅と非住宅の両方に「鉄筋RC」があるように、名前だけでは一意にならない）
- category_path: 工事種類の括り（VARCHAR、上の括りから順に「 > 」でつないだもの。この列で一意）
- parent_category: 一つ上の括り（VARCHAR、最上位の建設総合と構造別・用途別の15系列は NULL）
- level: 括りの深さ（INTEGER、1=建設総合と構造別・用途別の15系列、2=建築総合・建築補修・土木総合）
- period_start: 対象月（DATE、その月の1日）
- year / month: 年・月（INTEGER）
- fiscal_year: 年度（INTEGER、4月始まり）
- deflator: 建設工事費デフレーター（DOUBLE、2020年度平均 = 100）

工事種類は75系列です。建設総合の下に、建築（住宅・非住宅を構造別に）、建築補修、土木（公共事業とその他土木）が階層で並び、
上位の括りと内訳が同じ表にあります。道路2(再掲)・街路2(再掲)は他の系列を組み直した再掲です。
ほかに、上の括りを持たない構造別・用途別の15系列（W在来住宅、RC学校、S工場・倉庫など）があります。

見出しは8段で、括りが途中で終わる列は残りの段に同じ名前が繰り返し入っています。その他土木の内訳の「その他土木」は、
段を畳むと括りそのものの列と同じになるため、category_path を「建設総合 > 土木総合 > その他土木 > その他土木」としています。

ウエイトは2022年度までは各年度の建設投資の実績、2023年度以降は2020〜2022年度の平均を暫定的に使っています。

### テーブル: cost_deflator_fiscal_year

建設工事費デフレーター（年度次）です。1行 = 工事種類 × 年度で、1951年度から収録します。

- category_order / category / category_path / parent_category / level: 工事種類（cost_deflator_monthly と同じ75系列）
- fiscal_year: 年度（INTEGER）
- is_provisional: 暫定値か（BOOLEAN、公表資料で「（暫定）」が付いた年度は true）
- deflator: 建設工事費デフレーター（DOUBLE、2020年度平均 = 100）

古い年度ほど公表されている系列が少なく、公表されていない年度の行はありません。1951〜1959年度は治水・道路・公園・下水道などの土木の一部だけで、
建設総合は1960年度から、構造別・用途別の15系列は1990年度から、建築補修は2015年度からです。

### テーブル: design_labor_unit_price

公共工事設計労務単価です。1行 = 適用開始月 × 都道府県 × 職種で、2012年度の単価から改定ごとに収録します。
公共工事の予定価格の積算に使う建設技能者の日額単価で、所定労働時間内8時間当たりの円です。
時間外・休日・深夜の割増賃金と、法定福利費（事業主負担分）などの現場管理費・一般管理費は含みません。

- applied_from: 適用開始月（DATE、その月の1日。年度の表記で公表された2012・2013年度は4月1日）
- region: 地方連絡協議会（VARCHAR、北海道・東北・関東・北陸・中部・近畿・中国・四国・九州・沖縄）
- prefecture_code: 都道府県コード（VARCHAR、2桁）
- prefecture_name: 都道府県名（VARCHAR）
- occupation_code: 職種コード（VARCHAR、公表資料の「調査対象職種の定義・作業内容」の番号で01〜51）
- occupation: 職種（VARCHAR、2013年度までの「交通誘導員A・B」は交通誘導警備員A・Bにそろえている）
- unit_price: 設計労務単価（INTEGER、円）
- is_held_over: 前年度に据え置いた単価か（BOOLEAN）
- is_disaster_area_rate: 被災3県の括弧書きの単価か（BOOLEAN）

単価が設定されていない職種・都道府県は行がありません。屋根ふき工は2020年3月適用分から、
建築ブロック工は2014年2月適用分まで、タイル工は2017年3月・2018年3月適用分を除いて単価があります。

2021年3月・2022年3月適用分は、新型コロナウイルス感染症の影響下の特別措置として前年度を下回った単価を前年度に据え置いており、
公表資料で < > に囲まれた単価が is_held_over = true です。2022年3月適用分までの岩手県・宮城県・福島県には、
ほかと別に定めた単価があり、公表資料で ( ) に囲まれた単価が is_disaster_area_rate = true です。
2012年4月分は同年2月20日の臨時改定から適用している単価、2013年度以降は入札不調の発生状況等に応じた単価です。

2014年4月は同年2月の単価を引き続き適用すると告知されただけなので、行がありません。
岩手県・宮城県・福島県だけを対象にした2012年2月・6月の臨時の改定は、それぞれの適用開始月の行としては取り込んでいません。
2月の改定の単価は2012年4月分の括弧書きとして入っています。

## データ更新手順

main.py が箇所別基本表と時間帯別交通量表の CSV（47都道府県分）と区間形状の GeoJSON タイルを取得し、
タイルを区間ごとにまとめて Parquet にする。続けて不動産価格指数のページから「最新データ」の Excel の URL を資料名で引いて取得し、
シートごとの横持ちの表を縦持ちの Parquet にする。建設工事費デフレーターは統計表のページから月次・年度次の Excel をファイル名の接頭辞で引いて取得し、
工事種類が横に並ぶ表を縦持ちの Parquet にする。公共工事設計労務単価は案内ページから改定ごとの記者発表をたどって PDF を取得し、
単価表を縦持ちの Parquet にする。公表済みの PDF は差し替わらないので、取得済みのものは取り直さない。
そのうえで dbt build で各テーブルを再生成する。
ビルドは `bash scripts/build.sh` で実行する（Queria に公開する）。

タイルは配信元がディレクトリ一覧を返さないので、どのタイルがあるかを2段階で調べてリポジトリに置いている。

1. 候補の索引 tools/tile_index_z12.csv（`uv run python tools/build_tile_index.py`）。国土数値情報の都道府県境界に掛かる z12 タイルを8近傍に広げたもので、10,483タイルある
2. 実在するタイルの一覧 tools/tile_list_z12.csv（`uv run python tools/build_tile_list.py`）。候補を道路種別の6層すべてで叩き、配信されていたものだけを残す。6層で18,004枚ある

取得は2の一覧だけを、4本並列・全体で毎秒5リクエストまでの頻度で回す（約1時間）。候補を全部叩くと約6.3万リクエストになり、7割あまりは配信の無いタイルで 404 になる。GitHub のランナー（米国）からは1リクエスト 0.6 秒ほどかかるので、全部叩くと Sync の打ち切り（300分）に間に合わない。令和3年度のタイルは更新されないので、一覧は調査年度ごとに1回作れば足りる。

## ライセンス

国土交通省ウェブサイトのコンテンツに準拠する[公共データ利用規約（第1.0版）（PDL1.0）](https://www.mlit.go.jp/link.html)に従う。
道路交通センサス・可視化ツール・不動産価格指数・建設工事費デフレーター・公共工事設計労務単価は、同規約の[適用除外となるコンテンツの一覧](https://www.mlit.go.jp/page/kanbo01_hy_003657.html)に含まれていない。

出典:
「令和3年度全国道路・街路交通情勢調査 一般交通量調査」（国土交通省）（https://www.mlit.go.jp/road/census/r3/）を加工して作成。
「不動産価格指数」（国土交通省）（https://www.mlit.go.jp/totikensangyo/totikensangyo_tk5_000085.html）を加工して作成。
「建設工事費デフレーター」（国土交通省）（https://www.mlit.go.jp/statistics/details/t-other-2_tk_000362.html）を加工して作成。
「公共工事設計労務単価」（国土交通省）（https://www.mlit.go.jp/totikensangyo/const/1_6_bt_000217.html）を加工して作成。

箇所別基本表の列を英語名へ付け替えてコードに名称を付ける加工、時間帯別交通量表を時間帯ごとの縦持ちへ組み替える加工、
可視化ツールのタイルを区間ごとの形状にまとめて箇所別基本表へ結び付ける加工を行っている。
不動産価格指数は、Excel の地域ごとのシートを1つの表に縦持ちでまとめ、2008年3月以前の系列を除く加工を行っている。
建設工事費デフレーターは、工事種類ごとの列を縦持ちに組み替え、見出しの名前の半角カナ・全角英数を揃える加工を行っている。
公共工事設計労務単価は、PDF の単価表を縦持ちに組み替え、職種に公表資料の番号を付け、単価を囲む括弧をフラグの列に移す加工を行っている。
交通量・指数などの値そのものは改変していない。
