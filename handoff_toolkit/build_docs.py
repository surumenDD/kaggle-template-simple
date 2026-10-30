from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent
DOCS={
'00_最初に読む.md':r'''# 日本語化の引き継ぎキット

## このZIPの範囲を先に確認する

本ZIPは、**詳細仕様書・作業指示書・ローカル実行プログラム・テスト**の配布物である。講座固有の日本語訳、画面上の座標、時刻、元動画、生成済み音声は、このZIPには入っていない。既に保存されている「scripts_and_editing」で終わる編集データZIPを、別途ローカル入力として渡す必要がある。入力を推測で補うプログラムではない。

この区別は重要である。仕様書だけから元講座の全画面訳を復元することはできない。確定済みの訳文・表示座標・開始終了時刻が揃っている部分は、新たなOCR、ASR、翻訳モデル、映像内容分析なしで再実行できる。元の編集データで未確定の部分があれば、プログラムはその不足を報告し、確定済み部分だけを処理する。未確定箇所を一般的な日本語字幕に置き換えて「画面日本語化済み」と表示しない。

## 入力は3種類

1. このZIPを展開したフォルダ。
2. 既存の翻訳・編集データZIP。全講義の `voice_script.json`、保存済みの `japanese.ass`、`screen.json` 等があるもの。元データは変更しない。
3. 同じ録画版の元MP4。名称、長さ、解像度、フレーム数、SHA-256で対応を固定する。

既に日本語音声WAVがある場合は、対応する時刻付きJSON台本も一緒に渡す。WAVだけをファイル名で信用して自動流用しない。完成済みMP4は、再作成する必要がなければそのまま別に保管する。

## 最短の実行経路

Windows 11、Python 3.12、FFmpeg/FFprobeが利用可能なPCを想定する。PowerShellで次を実行する。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe finish.py --assets "D:\course\編集データ.zip" --sources "D:\course\元動画" --project "D:\course\project"
```

初回は公開フォントをローカルへ取得する。フォントファイルはこのZIPには同梱していない。Pythonパッケージの初回導入にもネット接続が必要である。一度導入した後、講座本文・映像・音声を外部へ送らずに実行できる。

既存の日本語音声25本等がある場合の例:

```powershell
.\.venv\Scripts\python.exe finish.py --assets "D:\course\編集データ.zip" --sources "D:\course\元動画" --audio-dir "D:\course\日本語音声" --paired-scripts "D:\course\日本語音声\台本" --project "D:\course\project"
```

終了コード0は「指定した再実行範囲が処理された」という意味であり、画面の韓国語がすべてなくなったという自動認定ではない。`reports/finish_status.json` と `reports/audit.json` を必ず確認する。

## Claude Codeに渡す文章

> このフォルダのCLAUDE.mdとSPECIFICATION_JA.mdに従い、同梱プログラムを実行してください。元動画の内容を再分析したり、台本を再翻訳・要約したりせず、既存の編集データを入力してください。最初に環境と入力を検証し、確定済みのデータだけで日本語音声と画面上書きのMP4を作成してください。失敗した講義は正確な理由とIDを記録し、独立して処理できる講義は続行してください。未確定の画面訳を捏造して完了扱いしないでください。元ファイルは変更せず、作成物の実体と検証レポートを確認して報告してください。

## 読む順番

`CLAUDE.md` → `SPECIFICATION_JA.md` → `RUNBOOK_WINDOWS.md` → 必要時 `DATA_CONTRACT.md` / `ACCEPTANCE_TESTS.md` / `TROUBLESHOOTING.md`。

このZIPの実装は合成テスト用の短い動画で検証する。実講座40本の全データをこのビルド環境へ渡して検証したものではない。実際に実施できたテストの結果は `build_evidence/` に保存される。元データのスキーマが仕様に一致しない場合は、無断変換せずエラーを返す。
''',
'CLAUDE.md':r'''# 実行担当エージェントへの指示

## 目的

既存の確定した台本・字幕・画面訳を、元の韓国語が表示された位置へ重ね、日本語ナレーション付きMP4として再現する。ユーザーは解説ではなく、実ファイルを必要としている。追加の意味解釈や企画を行わず、以下の手順を実行する。

## 最初に行うこと

- このZIPだけでは講座固有の訳文・座標・時刻は揃わないことを理解する。編集データZIPが同じ作業フォルダまたはユーザー指定位置にあるか調べる。複数版があれば、ユーザーが渡した最新の版を一つ選び、ファイル名・バイト数・SHA-256をログに記録する。複数版を勝手に混ぜない。
- PythonとFFmpeg/FFprobeの実体を検査する。導入済みなら再導入しない。パッケージ追加は専用venv内だけで行う。
- 原本の場所と出力の場所を分離する。入力MP4を書き換えない。過去の完成物も上書きしない。
- 初回は `finish.py --assets ... --sources ... --project ...` を実行する。途中再開は同じ `--project` を使う。

## 禁止事項

1. 未読の画面訳を「翻訳済み」とみなすこと。
2. `ja`、`ja_for_tts`、開始終了時刻を言語モデルで再生成すること。
3. ASSの時刻をさらに2倍すること。
4. 音声が収まらないとき、語句を削除・短縮・要約すること。
5. `-shortest`、無断の音声切断、音節の末尾切り捨てでエラーを隠すこと。
6. `screen.json`や`japanese.ass`がない講義に、画面下の字幕だけを付けて完成とすること。
7. 翻訳データ、講義映像、音声、個人情報をGitHub等の公開先へ送ること。
8. 有料API、クラウド計算資源、課金サービスを勝手に利用すること。
9. ブロックされた講義について証拠のないapproval.jsonを作成すること。
10. 旧台本に含まれる「作成中」や過去の進捗を、現在動いている処理として報告すること。

## 決められた実行順序

A. `python -m unittest -v test_toolkit` を実行。B. `init`で編集ZIPを安全に展開。C. `audit`で講義数・必須ファイルを検査。D. `font`で固定フォントを取得。E. 対応JSONが一致する既存WAVを流用し、不足分だけ音声化。F. 保存済みASSで再描画。G. 全フレーム・音声をデコード検査。H. 出力ハッシュを保存。I. `finish_status.json`に結果を確定。

初回に全40本のデコード確認を行うため、表示上進捗が静かな時間があり得る。プロセスの実行状態とログで判断する。無関係な再調査を始めない。

## 出力

`project/output/replay/<講義ID>_japanese.mp4` は既存翻訳計画の再現版。
`project/audio/<講義ID>/japanese.wav` は日本語ナレーション。
`project/assets/.../voice_script.json` は声を替えるための正本。
`project/reports/` は機械検証・不足リスト。

`replay`と`final`は区別する。`final`は内容校閲と画面網羅の証跡が別途存在する場合にのみ利用できる。ファイルの存在だけで翻訳の正確さや画面の網羅性を認定しない。

## 障害対応

障害は `TROUBLESHOOTING.md` の既知の手順だけで切り分ける。入力の意味を変える修正は行わない。同一コマンドを理由なく何度も繰り返さない。成功済みの中間ファイルとハッシュを保持する。続行できる独立した講義は続け、最後に失敗IDと理由を列挙する。

## 報告形式

実動画保存済み本数 / 対象本数、音声のみ本数、画面計画不足本数、検証失敗本数、成果物フォルダ、残る具体的作業を報告する。音声生成とMP4完成を混同しない。作業完了を宣言する前に対象全件の実体とレポートを照合する。
''',
'SPECIFICATION_JA.md':r'''# 既存翻訳計画を再現するための詳細設計・実装仕様

版: 1.0.0。対象: 1920×1080、60fps、講座が2倍速で再生された状態の元録画。目標: 同じ画素寸法の30fps・通常速度・日本語音声付きMP4。標準対象件数は40本。

## 1. 要求と非要求

主要求は、韓国語の表示位置に日本語を重ね、視線を別の場所へ移さず学習できること、韓国語の原音を日本語ナレーションへ置き換えること、後で声を替えられる時刻付き台本を残すこと、画質の劣化を抑えることである。

本キットが実装するのは、既に確定したデータの再現処理である。新規OCR、韓国語音声認識、翻訳、内容の推定、曖昧な語句の判断は行わない。欠落した訳文を「仕様から一意に得られる」とは扱わない。必要な情報は、訳文・位置・時間・覆い方・表示スタイルとして入力データに存在していなければならない。

## 2. 正本と優先順位

優先順位は、ユーザーが指定した編集ZIPの内部データ、同じZIPに含まれる確認記録、対応する元録画の実体、その他の過去の報告の順とする。過去の「完成済み」という文章より、保存されている実MP4と検証レポートを優先する。

日本語字幕は `captions.json` / SRT、日本語読み上げは `voice_script.json`、画面上書きは `screen.json` / ASSが担当する。元の字幕から読み上げを毎回作り直さない。`ja_for_tts`が非空なら読み上げはその文字列を一字も変えずに使う。`ja`は読める表示文であり、TTS用の仮名表記を字幕へ逆輸入しない。

本実装の映像経路では、保存済み `japanese.ass` を描画の正本として使う。JSONからASSを再構成する処理を推測で実装していない。ASSがない場合はその講義の映像出力を止める。screen.jsonは、画面訳計画の存在と凍結ハッシュを確認するために保持する。

## 3. ファイル構造

```text
作業フォルダ/
  toolkit.py / finish.py / test_toolkit.py
  CLAUDE.md / SPECIFICATION_JA.md / その他の文書
  requirements.txt / font_reference.json
project/
  project.json                  # 内容とファイル指紋の正本
  paths.local.json              # 元録画の絶対パス。配布ZIPには入れない
  environment.lock.json         # Python・FFmpeg等の実行環境
  assets/                       # 編集ZIPから取り出したテキスト類
  fonts/                        # 利用者PCで取得。再配布ZIPには入れない
  cache/tts/                    # 発話ごとの音声キャッシュ
  audio/<講義ID>/               # 全長WAV・発話WAV・音声検証
  work/<講義ID>/                # ASCII名のASSと作業用フォント
  output/replay/                # 保存済み計画の再現版
  output/final/                 # 内容校閲の証跡まである版
  approvals/                    # 内容校閲・網羅性確認の証跡
  logs/                         # エンコード・全編デコードのログ
  reports/                      # 対象一覧・不足・処理結果
```

元動画をprojectへコピーしない。必要なときに原本を読み取る。原本に対する書き込みは一切しない。

## 4. 時間軸の定義

元録画上の時刻を t、完成動画上の時刻を T とする。ここでは `T = 2.0 × t` である。voice_script.jsonの `start` と `end` は元録画の秒数。ASS/SRTは既に完成動画の秒数である。

例: JSONのstart=5.25、end=9.5なら、日本語音声の配置枠は10.5秒から19.0秒。既存ASSに10.5秒と書かれている場合、それを21秒へ変えてはならない。

音声の配列インデックスは `ROUND_HALF_UP(T × 48000)` で整数化する。Pythonの標準roundによる偶数丸めは使わない。半開区間 `[start_sample, end_sample)` を用いる。境界の判断は同じ丸め規則で統一する。

動画の時間はFFmpegの `setpts=2*(PTS-STARTPTS)` で変更する。音声が長いからといって講義全体のtime_scaleを自動変更しない。録画中に再生倍率が変わる、カットがある、可変フレームレート、別版の録画である等の場合は、この固定設計の対象外として止める。

## 5. 元動画の同一性

台本のsource_nameとファイル名が完全一致する原本を、指定ディレクトリ以下から探す。1本もなければ不足、2本以上あれば曖昧として停止する。短い部分一致で前半と後半を取り違えない。

初回取り込みでSHA-256、1920×1080、平均60fps、宣言60fps、デコードしたフレーム数、再生時間を記録する。source_durationとの差は0.35秒以下を許容する。これはコンテナと動画/音声ストリームの終端差を扱うためで、別内容の録画を許すためではない。フレーム数/60とコンテナの長さにも0.35秒以下の整合性を要求する。

動画ファイルを後で差し替えた場合、SHA-256が変わるので再開処理は止まる。映像内容を見て「同じようだ」と判断して通過させない。ファイル名だけを合わせた再エンコード版も自動受理しない。

## 6. 編集データの安全な取り込み

ZIP内の絶対パス、`..`、Windowsのドライブ指定、シンボリックリンクを拒否する。展開総量は8GiB、要素数は100,000を上限にする。展開対象はJSON・ASS・SRT・TXT・MD・CSVのみ。フォント、実行ファイル、Pythonスクリプトは取り込み時に実行せず、新キットにはコピーしない。

同名の要素が異なる内容で複数存在すれば停止する。同一講義IDに異なる台本が存在しても停止する。古いキャッシュと新しい翻訳を勝手に混ぜない。取り込み結果はハッシュで凍結し、後の処理時にも変更がないか確かめる。

## 7. 音声生成のバックエンド

既定は `pyopenjtalk-plus==0.4.1.post8` と、その配布物に含まれるHTS Voice Mei (mei_normal)である。Python側は `import pyopenjtalk` を用いる。TTSはローカルCPUで動く。大規模言語モデル、APIキー、VOICEVOXアプリを必須にしない。

呼び出しは `pyopenjtalk.tts(text, speed=1.0, run_marine=False, predict_nani=False)`。run_marineと追加のONNXによる読み推定は無効にして追加モデルへの依存を避ける。読みの正本はja_for_ttsである。生波形は48kHz・モノラル。非有限値、無音、予期しないサンプリング周波数を拒否する。

VOICEVOXに変更する場合はローカルエンジンのaudio_query/synthesisを使う別アダプターを実装できるが、本キットにそのアダプターは同梱していない。既存音声の流用とMeiによる再生成が実装済み経路である。実装していない機能を「対応済み」と扱わない。

## 8. 発話の配置と長さ調整

各発話の開始は台本のstart×2に固定する。締切はend×2。ただし次の発話まで30msの隙間を確保する必要があれば、次のstart×2−30msを締切とする。ナレーション区間自体が重なっている入力は受理しない。

TTS波形が枠に収まるならそのまま使う。長い場合だけFFmpegのatempoを使って音高を維持しつつ速度を上げる。必要速度は発話サンプル数 / (枠のサンプル数−960) とし、最低1.0。960サンプルは20msの収容余裕である。既定上限は1.65倍。この上限を超えたら停止し、講義IDと発話IDと必要倍率を記録する。

atempo後の実サンプル数を再読込する。枠から1サンプルでもはみ出す場合、trimで合わせず停止する。言い換え、短文化、助詞削除、文末削除、句読点除去で収めることを禁止する。音声を切らないことと、無条件に全発話を処理できることは別である。

最終WAVは発話の間を無音で埋め、元動画の長さ×2にする。最終発話が全長を超える場合も停止する。日本語の原稿をすべて読み上げる必要があるが、ナレーション対象から除外された発話を勝手に復活させない。narration_exclusionsは原データと確認記録に残す。

## 9. 音量とクリッピング

TTSの波形は符号付き16bitスケールとして扱う。絶対ピークが30,000を超えれば、その発話全体へ同じ縮小係数を掛ける。符号付き16bitの範囲外を単純clipして歪ませない。絶対ピークが1未満なら無音生成として失敗する。

この実装は全講座のLUFS統一を行わない。音量の主観的な揃いまで保証するものではない。音量調整を追加する場合は、全長WAVのコピーへ二段階loudnormを適用し、元のWAVとタイミングを保持する。変更は設定と検証に記録し、波形の末尾を切らない。

## 10. キャッシュと途中再開

発話キャッシュのキーには、読み上げ文字列、エンジン版、音声モデルSHA-256、話速、読み推定の設定を含める。異なる本文へ古い音声を再利用しない。講義単位の音声署名には台本全体、設定、モデル、FFmpeg実体のハッシュを含める。

音声の実ファイルとレポートのSHA-256が一致した場合のみスキップする。存在するだけではスキップしない。MP4も同様で、入力、音声、フォント、設定、環境の署名と出力ハッシュが一致したときだけ再利用する。

全体のfinish.pyは各講義の処理後に結果を一時ファイルへ書き、os.replaceで確定する。途中で止まっても、成功した音声や動画は保持される。失敗した講義は他の講義を止める理由にしない。ただし全体の対象件数が違う場合は、誤った資料の可能性があるので開始前に止める。

## 11. 既存音声の流用

既存WAVには、対応する `<講義ID>_voice_script.json` が必要。ファイル名は `<講義ID>_mei.wav` を受け付ける。voice_scriptの内容、時刻、source_name、source_duration、timeline_scaleから指紋を作り、取り込んだ正本の指紋と比較する。違えば流用しない。

48kHz・モノラル・16bit PCMであり、全長が期待値と0.5秒以内で合うことも要求する。流用時は波形を一切変更しない。既存の台本との対応という来歴を利用するもので、既存WAV全体の言語内容や全発話の時刻を新たに照合する処理ではない。レポートにその範囲を明記する。

## 12. 画面上書き

保存済みASSを一字も書き換えずに描画する。元の韓国語の位置へ背景マスクと日本語文字を置く責任は、ASSとscreen.jsonの既存計画にある。一般的な下字幕を追加して画面内文字の置換の代用にしない。

台本と画面訳は別である。画面内のメニューや図の説明には、ナレーションへ含めない日本語訳があり得る。そのため台本が全40本存在しても、画面の全訳が完了していることにはならない。

本実装はscreen.jsonの未知の構造を推測して再解釈しない。ASSが存在しても、全韓国語を覆っているかは機械的な存在検査だけでは認定できない。既存計画の再現可能性と、訳の網羅性をレポート上で分離する。

## 13. 字体とパスの扱い

Noto Sans CJK JP Regularの固定版を利用者PCへ取得し、font_reference.jsonのSHA-256を検証する。フォントはこのZIPとpack出力から除外する。利用者が自分の環境で取得する方式である。

Windowsのドライブ文字や日本語パスをFFmpegフィルタ文字列に直接埋め込むとエスケープ問題が起こりやすい。そのためASSとフォントを講義別workディレクトリへ置き、そこでASCIIの相対パス `overlay.ass` / `fonts` を指定する。元動画と出力先はshellを介さない引数配列で渡す。

## 14. 映像書き出し

既定はlibx264、CRF16、preset medium、yuv420p、30fps、AAC192kbps、48kHz、MP4 faststart。画面サイズを変更せず、cropやscaleも追加しない。元動画が通常の画面録画であることを前提とし、HDRや10bit等を暗黙に標準動画へ変換してよいとはしない。

色域・伝達特性・色行列・レンジが入力で明示されていれば出力へ引き継ぐ。ただしラベルの引継ぎは画素値同一を意味しない。文字を焼き込むため映像は再エンコードされる。CRF16は非可逆圧縮であり、元と完全に同じ画素値を保証しない。

入力60fpsの全フレームを、通常速度の30fpsで使う。出力でフレームが落ちたり重複したりしていないか、書き出し後に元との総フレーム数を比較する。fpsの表示値だけで判定しない。再生時間の許容差は0.5秒、平均fpsの許容差は0.02である。

`-shortest`は使わない。映像ストリームは元動画から、日本語音声はWAVから明示的にmapする。韓国語の元音声をデフォルトの再生トラックに残さない。既存の透かし・注意書きは無断で除去しない。

## 15. 音声だけの交換

すでに日本語画面が焼き込まれたMP4の声を替えるときは、映像を `-c:v copy` でコピーする。再描画をしない。新音声と動画の長さが0.5秒以上違う場合は止め、音声の末尾を切らない。

交換前後の映像パケットをFFmpeg hash muxerで比較し、圧縮された映像ペイロードのSHA-256が同じであることを確認する。コンテナ全体のSHA-256は音声交換により変わるので比較対象にしない。

画面内に旧音声のクレジットが焼き込まれている場合、それは音声だけの交換では直らない。新音声のクレジットは付属JSONと音声トラック名に記録する。旧表示の修正が必要なら、映像を変えないという条件とは両立しないので別の明示的編集として扱う。

## 16. 出力の確定

エンコード中は `.partial.mp4`。書き出し終了後に、FFmpegで映像と音声を全編デコードしてエラーがないことを確かめる。続いて解像度、fps、フレーム数、長さを検査する。合格後にだけ正規名へos.replaceで移す。

検証レポートを `.verified.json` として隣に置く。音声生成済み、エンコード済み、検証済み、内容の校閲済みは別の状態である。進捗報告ではそれぞれを分ける。

## 17. replayとfinal

replayは「既存の翻訳計画を機械的に再現した版」。すべての韓国語の消失や全訳の正確さを保証する名前ではない。入力の画面計画が一部しかなければ、その一部がそのまま再現される。

finalは、原本・ASS・画面計画・台本のハッシュと一致する確認証跡がある場合だけ許可する。approvalには確認者、根拠、画面の全範囲を確認したこと、訳文の確認が済んだこと、未解決項目が空であることが必要。エージェントが都合よくこれを捏造してはならない。

## 18. 品質検査の限界と役割分担

自動で検査できるのは、ファイル同一性、時刻の整合、音声長、サンプル数、欠落ファイル、重複ID、フレーム欠落、デコード失敗、出力形式等である。字幕の意味が講師の発言と一致するか、すべての小さな韓国語UIが訳されているか、誤字がないかを、このプログラムは新たに判定しない。

「再分析なし」を実現するには、その意味的な作業が済んだ固定データが入力に必要である。未確定の画面は不足として残す。正確な訳文・座標・時間のない箇所を、安いモデルの推測で補完することは本仕様に反する。

## 19. 再配布用の単一ZIP

利用者PCで編集データを取り込み、必要なら音声を生成した後、`toolkit.py pack --project ... --out ...` を実行する。仕様書、コード、確定した入力テキスト、全長日本語WAV、検証記録、ハッシュ一覧を一つのZIPにまとめる。

元のMP4、フォント、Python仮想環境、FFmpeg本体、絶対パスを含むpaths.local.json、発話ごとの巨大なキャッシュは含めない。ZIPのパス順と日時は固定する。Zip64を利用できるため4GiB超の音声データも扱える。作成後に全要素のCRCを検査する。

これで新しい作業者へ渡すものは、生成した統合ZIPと元MP4になる。ただしこのキット配布時点のZIPはその統合ZIPではない。既存の翻訳ZIPをこの実行環境では展開・統合できなかったため、入力データを別途渡す必要がある。

## 20. 再現性の水準

訳文と座標と時刻の再現性、同じ実装と設定での波形生成の再現性、MP4の全バイト一致は別である。前者は固定入力とハッシュで管理する。後者はPython、依存ライブラリ、音声モデル、FFmpeg/libass、フォント、OS、CPU、スレッド数の違いに影響され得る。

本キットは時間とデータ選択を決定論的にし、実行環境を記録し、得られた音声をキャッシュで固定する。同じ台本なら異なるOSでもMP4が完全に同じバイト列になる、という未検証の主張はしない。将来の再現では生成済みの日本語WAVと正確な入力一式を保管するのが最も確実である。
''',
'RUNBOOK_WINDOWS.md':r'''# Windowsでの実行手順

## 0. 用意する場所

`D:\course\handoff`にこのZIPを展開する。`D:\course\originals`に元MP4、`D:\course\assets.zip`に保存済みの翻訳・編集ZIPを置く。ZIPの中のさらにZIPを対象にしない。音声がある場合はWAVと時刻JSONを別のフォルダへ展開する。元動画を日本語版MP4と取り違えない。

空き容量は、元動画の容量に加え、日本語音声WAV、出力MP4、作業領域分が必要である。48kHz・16bit・モノラルPCMは1時間あたり約345.6MBである。40本の長い講座なら数GBから数十GBの余裕を確保する。計算式は `秒数 × 48000 × 2` バイト。実行前に全source_duration×2の合計から見積もる。

## 1. 環境の確認

```powershell
Get-Command py
py -0p
Get-Command ffmpeg
Get-Command ffprobe
ffmpeg -version
ffprobe -version
```

Python 3.12を推奨する。Python本体とFFmpeg/FFprobeがない場合は、公式配布元または信頼したパッケージ管理方法で導入する。実行担当は導入元と版を記録する。管理者権限を無断で要求せず、既存システムのPython環境を変更しない。

```powershell
cd D:\course\handoff
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest -v test_toolkit
```

PowerShellの実行ポリシーを変える必要はない。Activate.ps1を使わず、venv内のpython.exeを直接呼ぶ。

## 2. 最初の取り込みと監査

```powershell
.\.venv\Scripts\python.exe toolkit.py init --assets D:\course\assets.zip --sources D:\course\originals --project D:\course\project
.\.venv\Scripts\python.exe toolkit.py audit --project D:\course\project
```

`reports/audit.json`の件数・欠落を確認する。voice_script.jsonが40本存在することと、全40本の画面訳が完全であることを混同しない。スキーマや録画版の不一致で止まった場合は、画面内容を推測して補正しない。

## 3. フォントの準備

```powershell
.\.venv\Scripts\python.exe toolkit.py font --project D:\course\project
```

ネット接続が必要なのは取得時だけ。SHA-256が一致しないファイルを採用しない。フォントは利用者のPCで取得され、この配布ZIPには入っていない。

## 4. 一括処理と再開

```powershell
.\.venv\Scripts\python.exe finish.py --project D:\course\project
```

初回を一度に実行するなら:

```powershell
.\.venv\Scripts\python.exe finish.py --assets D:\course\assets.zip --sources D:\course\originals --project D:\course\project
```

同じコマンドを再実行すると、ハッシュが合う完成ファイルは再利用される。前回のプロセスがまだ動いている間に同じprojectへ二重起動しない。停止したプロセスの存在を確かめてから再開する。

## 5. 既存のMei音声を流用

```powershell
.\.venv\Scripts\python.exe finish.py --project D:\course\project --audio-dir D:\course\mei_audio --paired-scripts D:\course\mei_scripts
```

台本の指紋が一致しなければ流用せず、正本から再生成する。音声を全部生成済みでも、画面計画が不足している講義のMP4は止まる。音声のみを先に作る場合は`--audio-only`を付ける。

## 6. 講義を限定

`project.json`に記録されたidをそのまま指定する。

```powershell
.\.venv\Scripts\python.exe finish.py --project D:\course\project --lesson "course_S01_01,course_S01_02"
```

courseという文字は例であり、実際のIDはproject.jsonから使う。IDを部分一致で検索して別の講義を処理しない。

## 7. 声を替える

別の声で作成した、同じ全長・同じ配置の日本語WAVを用意する。入力動画は日本語画面を書き込んだ完成版。元の2倍速韓国語録画を指定しない。

```powershell
.\.venv\Scripts\python.exe toolkit.py revoice --video "D:\course\project\output\replay\course_S01_01_japanese.mp4" --audio "D:\course\new_voice.wav" --out "D:\course\revoiced.mp4"
```

映像ペイロードが変わっていないことを検査する。音声の長さが違うと止まる。画面内の旧クレジットまで修正する機能ではない。

## 8. 後任へ渡す統合ZIP

```powershell
.\.venv\Scripts\python.exe toolkit.py pack --project D:\course\project --out D:\course\localized_handoff_with_data.zip
```

この統合ZIPと元MP4が後任用の組である。展開後はtoolkit配下のスクリプトへ`--project ..\project --sources 元動画フォルダ`を指定する。環境依存のフォントは再取得する。必要なパッケージとFFmpegを導入してから実行する。

## 9. 最後に残すファイル

MP4、verified.json、credits.json、全長WAV、audio_report.json、voice_script.json、ASS、screen.json、project.json、audit.json、finish_status.json、environment.lock.jsonを保持する。素材を削除して容量を減らす場合も、原本・台本・画面計画・全長音声・検証結果は残す。
''',
'DATA_CONTRACT.md':r'''# 入力データ契約

## voice_script.json

トップレベルはJSONオブジェクト。必須: `source_name: string`、`source_duration: number`、`timeline_scale: 2.0`、`segments: array`。追加のcourse、voice_credit、caption_text_sha256、narration_selection_sha256、narration_exclusions、translation_review、pronunciation_overrides等は保持する。

各segmentの必須: id、start、end、ja。任意: ja_for_tts、caption_ids等。start/endは元録画の秒数で、0 <= start < end <= source_duration。idは講義内で一意。配列は時刻昇順で重なりなし。発話を配置する時刻だけが2倍される。本文や配列順を再解釈しない。

```json
{
  "source_name": "course_S01_01題名.mp4",
  "source_duration": 600.0,
  "timeline_scale": 2.0,
  "segments": [
    {"id": 1, "start": 5.25, "end": 9.5,
     "ja": "これは表示用の文章です。",
     "ja_for_tts": "これは表示用の文章です。", "caption_ids": [1,2]}
  ]
}
```

これは構造の例であり、実講座の代わりに使うダミー原稿ではない。

## japanese.ass

同じ講義ディレクトリに置く。PlayResX=1920、PlayResY=1080。Dialogue行が必要。時刻は完成動画秒数。文章・スタイル・背景マスク・座標・重なり順をそのまま保持する。既存ASSがない場合、台本だけから同じ位置の画面訳を生成することはできない。

## screen.json

画面内文字の翻訳計画。ここに記載される可能性があるtext_ja、原文、座標、背景色、表示時間等を正本として保持する。本実装は保存済みASSを使うため、このJSONの内部スキーマを新たに推定しない。実ファイルを確認できていないキーを、存在するものとしてコードから参照しない。

## captions.json / japanese.srt

確認用・将来の再編集用に保持する。SRTは出力時間軸。音声の正本をSRTへ置き換えない。字幕には表示しつつ読まない注記、複数字幕を一つにまとめた発話等があり、単純なSRT読み上げは既存選択を破壊し得る。

## 音声流用の契約

`<ID>_mei.wav` と `<ID>_voice_script.json` の組を渡す。source_name、source_duration、timeline_scale、segmentsの正規化JSONハッシュが現行台本と一致すること。48kHz、1ch、16bit PCM。音声全長と期待値の差は0.5秒以内。

## 内容確認証跡

次のJSONは形式例であり、自動でtrueへ書き換えてはいけない。

```json
{
  "source_sha256": "実原本のSHA256",
  "ass_sha256": "実ASSのSHA256",
  "voice_sha256": "実台本のSHA256",
  "screen_sha256": "実画面計画のSHA256",
  "screen_coverage_complete": false,
  "translation_review_complete": false,
  "unresolved_items": ["未確認箇所の実際の内容"],
  "reviewer": "確認した主体",
  "evidence": "確認記録のパスと対象範囲"
}
```

欠落キー、空の根拠、古いハッシュ、未解決項目があるものはfinalに通らない。
''',
'ACCEPTANCE_TESTS.md':r'''# 受入条件とテスト

## 本キットに含めた自動テスト

- 元秒→出力秒→サンプルの換算と半端サンプルの丸め。
- 講義の前半・後半IDの区別。
- 空や逆転した時刻・重複ID・重なりの拒否。
- ナレーション本文の変更による指紋更新。
- ZIPパストラバーサルとフォント・コードの取り込み除外。
- ASSの時刻を再スケールしないこと。
- finalの確認証跡なしでの失敗。
- 16bitのオーバーフローを避ける波形変換と無音TTSの拒否。
- 合成した1920×1080/60fps/2秒の動画、短い日本語台本、ASSによる一連の取り込み→実TTS→描画→全編デコード。
- 120フレームが30fpsの出力でも120フレームであること。
- 音声差し替え前後の圧縮映像ペイロード一致。
- 統合ZIPのCRCとフォント非同梱。

実施結果はbuild_evidence内を参照する。テストの数を実講座の確認本数と解釈しない。

## 各講義の機械的受入

原本SHA-256一致、台本とASSの凍結ハッシュ一致、日本語音声実体あり、必要な画面計画あり、エンコード終了、全映像・全音声デコード成功、解像度1920×1080、平均30fps、元と同じフレーム数、長さ差0.5秒以内、MP4ハッシュ記録、レポート保存をすべて満たすこと。

生成音声では全発話の生成、枠への収容、切り捨てなし、重なりなしを確認する。既存音声の流用は来歴と台本指紋に基づく別の検証範囲であり、新規TTSと同じ全発話検査済みという表示をしない。

## 内容面の受入

画面に存在した韓国語のうち対象に含めた文字が漏れなく訳され、訳が同じ位置にあり、操作の説明と同期し、重要なイラストやカーソルを不必要に覆わず、既存字幕と重ならず、誤訳の修正根拠が記録されていること。これらは確定済みの画面計画・校閲記録に依存する。ファイルの件数だけでは証明できない。

全40本のfull-completionを宣言するには、対象40件が同じ入力版と対応し、各finalの証跡と実MP4が揃っていること。1本でも音声のみ、仮訳、画面未確認、未保存、デコード未検証があれば、それを残件にする。

## 推奨する目視確認位置

各講義の冒頭注意書き、最初の発話、初めて画面訳が出る時刻、画面構成が切り替わる時刻、長い文、最終発話、最後の3秒。代表場面の検査は全フレーム検査ではない。代表場面だけで「全韓国語を確認した」と記録しない。

## 画質比較

画面の意図的変更領域を除外して原本フレームと出力フレームを対応させて比較する。字幕領域を含めた全画面PSNR低下を圧縮劣化と誤解しない。逆に、代表場面のPSNRが高いことを全編無劣化の証拠としない。今回の既定はCRF16の高品質再圧縮であり、可逆保存ではない。
''',
'TROUBLESHOOTING.md':r'''# 障害と固定対応

| 検出内容 | 意味 | 実行担当が行うこと |
|---|---|---|
| No voice_script.json | 入力ZIPが違う/データがない | 編集データZIPを確認。原稿を捏造しない |
| Missing script field | スキーマが違う | 実ファイルのキーと仕様を比較して記録。別の時刻単位へ無断変換しない |
| Conflicting scripts | 複数版が混在 | 最新の正本1版へ戻る。本文を合成しない |
| expected one exact source | 原本不足/重複 | 指定フォルダと正確な名前を修正 |
| Source SHA changed | 別録画/再エンコード/改変 | 元の同一ファイルを用意 |
| source is not 60 fps CFR | 時間軸前提が違う | 自動で30fpsへ間引かない。対象録画を確認 |
| missing screen/ASS plan | 画面訳計画の欠落 | 音声作成を進める。MP4は不足として残す |
| required speed exceeds | 発話が枠に入らない | 発話IDと必要倍率を報告。文を削らない |
| audio still overflows | 時間伸縮後も長い | 切り捨てない。設定変更には根拠が必要 |
| Font download hash mismatch | 違うフォント版/取得異常 | 採用しない。公式URLと固定版を確認 |
| ffmpeg not found | 実行環境不足 | FFmpegとFFprobeを信頼した手段で導入、PATHを確認 |
| Missing ass filter | libass非対応ビルド | libass付きFFmpegへ切り替え、版とハッシュを記録 |
| Frame loss/duplication | 出力フレーム数不一致 | finalへ昇格しない。エンコードログとfps設定を点検 |
| Audio/video duration mismatch | 別時間軸/違う音声 | 日本語版MP4と同じ全長WAVか確認 |
| final coverage approval missing | 内容校閲の証跡なし | replayを作成し、finalの完了と混同しない |

## 入力の修正が必要な場合

このキットは凍結後のJSONやASS変更を検出して止める。修正版を作るなら元の正本を保持し、新しい編集ZIPを作り、別のprojectへ取り込む。ハッシュを都合よく上書きして変更検査を回避しない。

## テストに通るのに実講座で失敗する場合

合成テストはコーデックと処理ロジックの検証であり、未展開の実講座40本のデータ契約を保証するものではない。実データの形が異なる場合は、エラーの講義IDとキーの差を保存する。意味の再推定が要る問題と、単なる形式の変換を区別する。安いモデルに語句を想像して埋めさせない。

## 同時実行しない

同じprojectを二つのプロセスで処理しない。現在の実装には排他ロックがない。講義単位の並列化が必要な場合も、別projectまたは明示的に分離した作業ディレクトリを使用する。並列化のために元データやキャッシュの整合性を犠牲にしない。
''',
'SOURCES_AND_SCOPE.md':r'''# 実装根拠・ライセンス・検証範囲

## 一次資料

- FFmpeg CLI: https://ffmpeg.org/ffmpeg.html
- FFmpeg filters (setpts, ass, atempo): https://ffmpeg.org/ffmpeg-filters.html
- pyopenjtalk-plus固定実装: https://github.com/tsukumijima/pyopenjtalk-plus/tree/v0.4.1-post8
- pyopenjtalk-plus配布: https://pypi.org/project/pyopenjtalk-plus/0.4.1.post8/
- Noto CJK固定版: https://github.com/notofonts/noto-cjk/tree/Sans2.004
- VOICEVOX ENGINE API (将来の別アダプター参照のみ): https://voicevox.github.io/voicevox_engine/api/

フォントを同梱しない。利用者PCで取得する。Meiの生成音声を利用する場合は、音声のクレジットと該当ライセンスを保持する。パッケージに含まれる各依存物のライセンスは、それぞれの配布物を確認する。

本配布物に講座の本文、訳文、映像、生成済み講座音声は含まれない。ローカルの私的な入力として読み取る。講座データを公開リポジトリへアップロードしない。実行コードのビルド・合成テストには、一般的な短いテスト文と単色動画のみを使う。

## 未実施の検証

全講座の翻訳校閲、全画面の網羅性確認、元編集ZIP内の全スキーマ確認、実講座40本のエンドツーエンド処理、Windows実機でのエンドツーエンド試験は、この配布ビルドでは未実施である。

## 実施結果の所在

build_evidence/test.log、test_result.json、environment.json、requirements-lock.txtを参照する。成功/失敗はファイルの実値で確認する。説明文だけで成功扱いしない。
'''
}
for name,text in DOCS.items():(ROOT/name).write_text(text.strip()+'\n',encoding='utf-8')
(ROOT/'requirements.txt').write_text('numpy==2.2.6\npyopenjtalk-plus==0.4.1.post8\n',encoding='utf-8')
(ROOT/'START_WINDOWS.cmd').write_text('@echo off\r\ncd /d "%~dp0"\r\necho Read 00_*.md and RUNBOOK_WINDOWS.md before processing.\r\npy -3.12 -m venv .venv\r\nif errorlevel 1 exit /b 1\r\n.venv\\Scripts\\python.exe -m pip install -r requirements.txt\r\nif errorlevel 1 exit /b 1\r\n.venv\\Scripts\\python.exe -m unittest -v test_toolkit\r\npause\r\n',encoding='ascii')
(ROOT/'PACKAGE_SCOPE.json').write_text(json.dumps({'type':'specification_and_runner_only','includes_private_course_annotations':False,'includes_original_videos':False,'includes_existing_narration_audio':False,'includes_font_files':False,'requires_separate_existing_editing_archive':True,'actual_course_end_to_end_tested':False,'semantic_gap_policy':'fail_closed_do_not_invent_translations'},indent=2)+'\n',encoding='utf-8')
print('Wrote',len(DOCS),'documents.')
