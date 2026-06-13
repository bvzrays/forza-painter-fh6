<p align="center">
  <img src="https://github.com/user-attachments/assets/d4f48f71-d76e-4ffe-9fb1-0b075d79bf05" alt="forza-painter FH6 logo" width="720">
</p>

<h1 align="center">forza-painter FH6</h1>

<p align="center">
  <strong>이미지를 Forza Horizon 6 비닐 그룹 레이어로 변환하고 가져오는 도구입니다.</strong>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">中文</a> ·
  <a href="README.ko-KR.md">한국어</a>
</p>

<p align="center">
  <code>v1.8.4</code> · <code>Windows</code> · <code>Forza Horizon 6</code> · <code>GPU/OpenCL</code> · <code>One-file EXE</code>
</p>

PNG/JPG/BMP 이미지를 Forza Horizon 6 비닐 그룹 레이어로 변환합니다. 앱에서 생성, 미리보기, 가져오기를 한 번에 처리하며 일반 사용자는 Python, `.venv`, 배치 파일, 메모리 주소 입력이 필요 없습니다.

> **EXE 다운로드:** [Releases](https://github.com/bvzrays/forza-painter-fh6/releases)에서 `forza-painter-fh6-v1.8.4.exe`를 내려받아 바로 실행하세요.

> **프리셋 마켓:** https://painter6.com 에서 공유 이미지, 프리셋, JSON 패키지를 둘러보거나 앱 안의 새 마켓 배너로 바로 열 수 있습니다.

> **결과가 흐릿하면:** 먼저 `Random samples` 값을 높이세요. **200000** 이상부터 품질 차이가 크게 보이는 경우가 많습니다.

> **가져오기는 시간이 걸릴 수 있습니다:** v1.4.1부터 여러 FH6 템플릿 위치 찾기 방식을 시도하며 최대 5분 정도 걸릴 수 있습니다. FH6를 Vinyl Group Editor에 그대로 두고 메뉴를 바꾸지 마세요.

| 기능 | 설명 |
| --- | --- |
| JSON 생성 | 내장 GPU/OpenCL 생성기로 이미지를 geometry JSON으로 변환합니다. |
| 미리보기 | 원본 이미지와 생성된 geometry를 앱에서 확인합니다. |
| FH6 가져오기 | 현재 열려 있는 FH6 Vinyl Group Editor에 JSON을 가져옵니다. |
| 안전한 쓰기 | 쓰기 전에 편집 가능한 레이어 테이블을 자동으로 찾고 검증합니다. |
| 프리셋 마켓 | 앱에서 https://painter6.com 을 열어 공유 이미지, 프리셋, JSON 패키지를 둘러봅니다. |
| 업데이트 확인 | 시작 시 새 버전을 확인하고 변경 내역을 표시합니다. |

## 빠른 시작

1. [Releases](https://github.com/bvzrays/forza-painter-fh6/releases)에서 `forza-painter-fh6-v1.8.4.exe`를 내려받습니다.
2. EXE를 쓰기 가능한 일반 폴더에 둡니다. 예: `Desktop\forza-painter-fh6`.
3. EXE를 더블 클릭합니다. FH6 가져오기에서 Windows가 프로세스 접근을 막으면 관리자 권한으로 실행하세요.
4. FH6에서 `Create Vinyl Group` / `Vinyl Group Editor`를 열고 sphere 템플릿을 불러온 뒤 `Ungroup`합니다.
5. 앱에서 JSON을 생성하고 `Import` 페이지에서 실제 템플릿 레이어 수를 입력한 뒤 가져오기를 실행합니다.

개발 목적이 아니라면 GitHub의 자동 `Source code` ZIP을 받을 필요가 없습니다. 일반 사용자는 `.exe`만 사용하세요.

## 미리보기

<table>
  <tr>
    <td align="center" width="50%">
      <img src="docs/screenshots/app-import-preview.png" alt="App import page"><br>
      <strong>App import page</strong>
    </td>
    <td align="center" width="50%">
      <img src="docs/screenshots/fh6-template-ready.png" alt="FH6 template ready"><br>
      <strong>Template ready in FH6</strong>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%">
      <img src="docs/screenshots/fh6-import-result.png" alt="FH6 import result"><br>
      <strong>Imported result</strong>
    </td>
    <td align="center" width="50%">
      <img src="docs/screenshots/fh6-car-applied.png" alt="FH6 car applied result"><br>
      <strong>Applied to car</strong>
    </td>
  </tr>
</table>

## JSON 생성

1. `Generate JSON` 페이지를 엽니다.
2. `Add images`를 클릭하고 PNG/JPG/BMP 이미지를 선택합니다.
3. 품질 프리셋을 선택합니다.
4. 필요하면 `Use custom settings`를 켜고 출력 레이어, 해상도, 무작위 샘플, 변형 샘플을 조정합니다.
5. 하단의 `Start generating` 버튼을 클릭합니다.
6. 미리보기와 로그가 업데이트될 때까지 기다립니다.

생성된 파일은 원본 이미지 옆에 저장됩니다. 예: `image.500.json`, `image.1000.json`, `image.3000.json`.

템플릿 레이어 수와 가장 잘 맞는 높은 레이어 JSON을 사용하는 것이 좋습니다. 3000 레이어 템플릿에는 `image.3000.json` 또는 최종 `image.json`을 사용하세요.

| 프리셋 | 출력 레이어 | 무작위 샘플 | 용도 |
| --- | ---: | ---: | --- |
| extremely fast | 500 | 30000 | 빠른 구도 확인 |
| fast | 1000 | 60000 | 빠른 초안 |
| balanced | 1800 | 120000 | 기본 권장값 |
| slow | 2500 | 220000 | 완성용 품질 |
| super slow | 3000 | 350000 | 가장 선명하지만 매우 느림 |

## JSON 가져오기

1. FH6를 실행하고 `Vinyl Group Editor`를 열어 둡니다.
2. 단순한 sphere 레이어가 많은 템플릿을 불러오거나 만듭니다.
3. 템플릿을 `Ungroup`하고 게임에 표시되는 실제 레이어 수를 확인합니다.
4. 앱의 `Import` 페이지에서 `Refresh`를 누르고 `forzahorizon6.exe`를 선택합니다.
5. 실제 템플릿 레이어 수를 입력합니다.
6. 생성된 `.json`을 추가하거나 `Use generated JSON`을 클릭합니다.
7. 고급 주소 입력칸은 비워 두고 `Import JSON`을 클릭합니다.

FH는 커버 저장과 적용 범위를 위해 4개의 추가 경계 레이어가 필요합니다. 예: 1000 레이어 JSON에는 최소 1004 레이어 템플릿을 사용하는 것이 좋습니다.

## 실험적 영역 페인트 (Region Paint)

영역 페인트는 반복식 페인팅 워크플로로, 전체 이미지에 기본 레이어 패스를 먼저 생성한 후 사각형 또는 타원 도구로 영역을 선택하여 해당 영역에만 추가 세부 레이어를 적용합니다.

- 단일 이미지를 추가하고, 품질 프로필을 선택하면(`stopAt`에 따라 총 예산이 설정됨) 첫 번째 패스 및 영역 레이어를 조정합니다.
- `Start First Pass`를 클릭하여 기본 레이어를 생성합니다. 오른쪽 캔버스에 미리보기가 표시됩니다.
- 왼쪽 캔버스에서 사각형 또는 타원 도구로 선택 영역을 그립니다. 빨간색 오버레이가 선택 영역을 표시합니다.
- `Paint Selected Region`을 클릭하여 선택한 영역에만 추가 레이어를 추가합니다. 각 영역마다 반복할 수 있습니다.
- 모든 패스가 끝나면 `Open Result Folder` 또는 `Save Result JSON`을 사용하여 최종 `base.json`을 얻습니다.
- 일반 생성과 동일하게 `Import` 탭에서 결과 JSON을 가져옵니다.
- 남은 예산은 `Remaining` 옆에 표시됩니다. 각 영역 패스마다 예산에서 레이어가 소비됩니다.

## 중요 규칙

- 템플릿은 반드시 Ungroup되어 있어야 합니다.
- 앱에 입력한 레이어 수는 게임과 정확히 같아야 합니다.
- 가져오기 중에는 게임 메뉴를 전환하지 마세요.
- FH6를 다시 시작하거나 템플릿을 다시 불러온 경우 새 레이어 수로 다시 가져오세요.
- JSON 레이어가 템플릿보다 적으면 남는 템플릿 레이어는 숨겨집니다.
- JSON 레이어가 템플릿보다 많으면 초과 shape는 잘립니다.
- 투명 PNG 배경은 보이는 배경색으로 가져오지 않습니다.

## 런타임 파일 위치

단일 EXE는 내부 파일을 임시로 풀고 일반 런타임 데이터는 EXE 밖에 저장합니다. 정확한 위치는 시작 로그에서 확인할 수 있습니다.

EXE 옆에 생길 수 있는 외부 폴더:

- `runtime/`: 로그, 세션 데이터, 임시 파일.
- `webui-data/`: 로컬 브라우저/UI 캐시.

앱을 닫은 뒤 이 폴더를 삭제하면 로컬 런타임 데이터를 초기화할 수 있습니다.

## 문제 해결

- **FH6 가져오기가 안 됨:** 앱을 닫고 EXE를 관리자 권한으로 실행하세요.
- **GPU/OpenCL 오류:** NVIDIA/AMD/Intel 그래픽 드라이버를 업데이트하세요. 내장 생성기는 OpenCL을 사용합니다.
- **템플릿을 찾을 수 없음:** Vinyl Group Editor에 있는지, 템플릿이 Ungroup되었는지, 레이어 수가 정확한지 확인하세요.
- **가져온 결과가 흐림:** 더 높은 레이어 JSON을 사용하거나 `Output layers` / `Random samples`를 높이세요.
- **디버깅이 필요함:** 앱에서 `Export detailed log`를 실행하고 로그를 이슈에 첨부하세요.

## 리소스

- 가져오기 참고 영상: https://www.bilibili.com/video/BV1hG5Z6nENZ
- 프리셋 마켓: https://painter6.com
- 내장 GPU 생성기 출처/참고: https://github.com/zjl88858/forza-painter-geometrize-gpu
- 전체 변경 기록: [CHANGELOG.md](CHANGELOG.md)

## 변경 기록

여기에는 버전 번호가 있는 릴리스만 남깁니다. 앱 업데이트 안내에 쓰이는 전체 기록은 [CHANGELOG.md](CHANGELOG.md)를 참고하세요.

### v1.8.5 / 2026-06-13

- **영역 페인트 예산 가드**: 첫 패스 레이어가 총 예산을 초과할 때 `Start First Pass`를 클릭하거나, 사용된 레이어 + 영역 레이어가 총 예산을 초과할 때 `Paint Selected Region`을 클릭하면 이제 명확한 로그 경고를 표시하고 예산 초과를 조용히 넘기지 않고 중단합니다.
- **다방향 드래그 지원**: 영역 페인트의 사각형 및 타원 선택 도구가 이제 모든 방향(예: 우하→좌상)으로 드래그할 수 있습니다. 이전에는 좌상→우하 방향이 아닌 드래그 시 마스크 생성 오류가 발생했습니다.
- **마스크 지우기 개선**: `Clear All` 버튼(기존 "Clear Mask"에서 이름 변경)이 모든 선택 마스크를 제거합니다. 새로운 `Clear Selected` 버튼은 현재 선택된 마스크만 삭제하며, 선택된 마스크가 없으면 힌트를 기록합니다.
- **작은 화면 접근성**: 노트북 사용자가 하단 버튼이 화면 밖에 있을 때도 결과 작업에 접근할 수 있도록, 스크롤 가능한 Step 3 영역에 `Open Result Folder` 및 `Save Result JSON` 중복 버튼이 "(for small screens)" 힌트와 함께 추가되었습니다.

### v1.8.4 / 2026-06-07

- 영역 페인트(Region Paint) 선택 도형에 **드래그 이동**, **모서리 크기 조절**, **회전**(슬라이더, 스크롤 휠, 입력창 또는 캔버스 핸들) 기능을 추가했습니다.
- 비교적 적은 연산으로 좋은 결과를 얻을 수 있는 추천 프리셋을 추가했습니다.

### v1.8.3 / 2026-06-06

- 영역 페인트(Region Paint) 캔버스에 **히트맵** 탭을 추가했습니다. 생성된 이미지의 모양 밀도를 색상 스케일 바로 보여주며, 각 패스 후 자동 생성되고 탭 전환 시 즉시 표시되도록 캐시됩니다.
- 영역 페인트 미리보기 이미지 생성 속도를 대폭 개선했습니다.

### v1.8.2 / 2026-06-06

- 영역 페인트(Region Paint)의 3단계 선택 도구에서 페더(Feather) 컨트롤을 제거했습니다. 선택 마스크는 이제 항상 하드 엣지(0 페더)로 적용되어, 페더로 인해 선택 영역 페인트 기능이 비정상적으로 작동하던 문제를 수정했습니다.

### v1.8.1 / 2026-06-05

- 영역 페인트(Region Paint) 추가 — 새로운 반복식 페인팅 워크플로. 전체 이미지에 기본 레이어 패스를 생성한 후, 사각형 또는 타원 도구로 영역을 선택하여 해당 영역에만 추가 레이어를 세부 조정할 수 있습니다. 레이어 예산 관리, 패스 기록, 실시간 미리보기 캔버스, 결과 JSON 내보내기를 포함합니다.
- 창 하단의 로그 영역이 Notebook 탭에 의해 부분적으로 가려지는 문제를 수정했습니다.

### v1.8.0 / 2026-06-01

- 앱 버전을 `v1.8.0`으로 업데이트했습니다. 릴리스 파일은 이제 `forza-painter-fh6-v1.8.0.exe`를 사용합니다.
- 실험적 전체 도형 가져오기/내보내기 흐름을 추가했습니다. 전체 도형 가져오기는 `Import` 페이지에 있고, 현재 게임 그룹 내보내기는 `Export` 페이지에 있습니다.
- 전체 도형 가져오기/내보내기는 레이어 오프셋 `0x7A`의 16-bit shape word를 사용하고 `0xA8` 같은 휘발성 리소스 포인터를 복사하지 않습니다.
- type-code JSON 지원을 위해 Kloudy's FH6 Painter custom-importer 표기와 글꼴 shape registry를 포함했습니다.

### v1.7.0 / 2026-06-01

- 앱 버전을 `v1.7.0`으로 업데이트했습니다. 릴리스 파일은 이제 `forza-painter-fh6-v1.7.0.exe`를 사용합니다.
- 생성, 가져오기, 도구, 튜토리얼 페이지에 눈에 띄는 프리셋 마켓 배너를 추가했습니다.
- 새 마켓 버튼은 https://painter6.com 을 열어 공유 이미지, 프리셋, JSON 패키지를 앱에서 바로 둘러볼 수 있게 합니다.

### v1.6.8 / 2026-05-28

- 앱 버전을 `v1.6.8`로 업데이트했습니다. 릴리스 파일은 이제 `forza-painter-fh6-v1.6.8.exe`를 사용합니다.
- 최신 GitHub `main` 변경 사항을 반영해 타원의 너비/높이를 소수 값으로 유지하며, 게임 내 가져오기 정확도를 높였습니다.
- 미리보기 영역에 v1.6.8은 게임 내 결과를 우선하고 미리보기는 근사치라는 안내를 추가했습니다.
- JSON 미리보기에 supersampling을 적용해 소수 크기 타원이 미리보기에서 더 거칠게 보이는 문제를 줄였습니다.

### v1.6.7 / 2026-05-27

- 앱 버전을 `v1.6.7`로 업데이트했습니다. 릴리스 파일은 이제 `forza-painter-fh6-v1.6.7.exe`를 사용합니다.
- 번들 GPU 생성기를 upstream `canary-26052702`로 업데이트했습니다.
- FH6 가져오기 스케일의 magic number를 원형/사각형 기준 크기 상수로 바꿔 게임 내 원형 기준 크기를 명확히 조정할 수 있게 했습니다.
- 버퍼링된 생성기 출력이나 속도 변화 때문에 남은 시간이 크게 빗나가지 않도록 생성 ETA 추정을 개선했습니다.

### v1.6.6 / 2026-05-26

- 앱 버전을 `v1.6.6`으로 업데이트했습니다. 릴리스 파일은 이제 `forza-painter-fh6-v1.6.6.exe`를 사용합니다.
- 번체 중국어 UI 번역을 추가하고 언어 선택기 레이아웃을 개선했습니다.
- RGB 이미지의 `luma_band` 전처리를 수정하고 전처리 이미지 저장을 더 안전하게 만들었으며, geometry/color 데이터 테스트를 추가했습니다.
- 단일 EXE에 OpenCV와 NumPy를 포함하여 release 빌드에서도 `luma_band` 전처리가 작동합니다.
- 가져오기 전에 FH6 템플릿 레이어 수 입력을 필수로 하여 빈 레이어 수로 인한 자동 찾기/가져오기 실패를 줄였습니다.
- typed exception과 공용 유틸리티 헬퍼로 핵심 모듈을 정리했습니다.

### v1.6.5 / 2026-05-25

- 앱 버전을 `v1.6.5`로 업데이트했습니다. 릴리스 파일은 이제 `forza-painter-fh6-v1.6.5.exe`를 사용합니다.
- 번들 GPU 생성기를 upstream `v1.2-Canary-20260525`로 업데이트했습니다.
- 기본 제공 프리셋은 이제 기본값으로 `forceOpaqueShapes = false`를 사용합니다.
- 생성기 실행 중 메인 앱 오버헤드를 줄였습니다. 정리된 생성기 환경, 느린 파일 폴링, 가장 무거운 프리셋의 덜 빈번한 미리보기 쓰기를 사용합니다.
- 전처리가 별도 입력 이미지를 만들 때 생성된 출력 파일 추적이 잘못되는 문제를 수정했습니다.

### v1.6.1 / 2026-05-24

- 앱 버전을 `v1.6.1`로 업데이트했습니다. 릴리스 파일은 이제 `forza-painter-fh6-v1.6.1.exe`를 사용합니다.
- 기본 제공 프리셋에서 `luma_band` 전처리를 기본 비활성화했습니다.
- 가져오기 시 `webui-data`의 오래된 FH6 세션 위치 데이터를 재사용하지 않고, 쓰기 전에 현재 템플릿을 다시 찾습니다.
- JSON 미리보기는 패키징 환경별 타원 왜곡 차이를 줄이기 위해 안정적인 단일 렌더러 경로를 사용합니다.

### v1.6.0 / 2026-05-24

- 앱 버전을 `v1.6.0`으로 업데이트했습니다. 릴리스 파일은 이제 `forza-painter-fh6-v1.6.0.exe`를 사용합니다.
- 내장 GPU 생성기를 upstream `canary-26052401`로 업데이트했습니다.
- upstream `errorGridSize` 프리셋 지원을 반영했습니다.
- 투명 영역으로 도형이 넘치는 것을 줄이는 upstream 알고리즘 조정을 반영했습니다.
- 투명 이미지 하단의 큰 타원 생성 품질이 크게 개선되었습니다.

### v1.5.4 / 2026-05-23

- 고해상도 원본 이미지, 생성기 미리보기 PNG, JSON 미리보기가 현재 미리보기 패널에 맞게 비율을 유지하며 표시되도록 수정했습니다.
- JSON 미리보기에서 type 16 회전 타원이 납작해지거나 잘못 회전되어 보이던 문제를 수정했습니다.

### v1.5.3 / 2026-05-22

- 단일 EXE용 사용자 프리셋 가져오기, 이미지/JSON 목록 제거, checkpoint 재사용, 출력 이름 수정, Pillow 미리보기 fallback을 추가했습니다.

### v1.5.2 / 2026-05-22

- 일반 사용자가 Python, `.venv`, helper 파일 없이 사용할 수 있는 단일 EXE를 추가했습니다.
- GUI EXE가 가져오기와 FH6 메모리 탐색을 위해 숨겨진 helper 모드로 자기 자신을 다시 실행할 수 있습니다.
- Tools 페이지와 시작 로그에 외부 런타임/캐시 위치를 표시합니다.

### v1.5.1 / 2026-05-22

- 프로젝트 `.venv`에 `pip`가 없는 경우 의존성 설치가 실패하던 문제를 수정했습니다.
- 소스 패키지의 누락 파일 진단 메시지를 개선했습니다.

### v1.5.0 / 2026-05-22

- 내장 GPU/OpenCL 생성기를 upstream `canary-26052102`로 업데이트했습니다.
- upstream PR #4의 work-group evaluation 알고리즘을 추가했습니다.
- 시작 시 업데이트 확인, 루트 `CHANGELOG.md`, 어두운 데스크톱 UI를 추가했습니다.

### v1.4.1 / 2026-05-21

- FH6 템플릿 자동 찾기가 v1.3 및 v1.4 스캔 방식을 모두 시도합니다.
- RTTI vtable fallback을 추가하고 자동 찾기 대기 시간을 늘렸습니다.

### v1.4.0 / 2026-05-21

- 50000자 제한의 자세한 로그 내보내기를 추가했습니다.
- 큰 쓰기 가능 메모리 영역에 대한 FH6 템플릿 자동 찾기를 개선했습니다.

### v1.3.0 / 2026-05-21

- 내장 GPU/OpenCL 생성기를 upstream `canary-26052101`로 업데이트했습니다.
- GPU 선택 수정과 선택된 OpenCL 장치 로그를 추가했습니다.

### v1.2.0 / 2026-05-20

- 내장 GPU/OpenCL 생성기를 upstream `canary-26052001`로 업데이트했습니다.
- 내장 및 사용자 생성 설정에 `forceOpaqueShapes = true`를 명시했습니다.

### v1.1.1 / 2026-05-20

- 앱 창, CLI, 릴리스 패키지 이름에 중앙 버전 관리를 추가했습니다.
- 저장소 구조와 릴리스 패키징을 정리했습니다.
