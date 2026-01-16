# EBS 라디오 녹음 시스템 (EBS Radio Recorder)

Cloudflare Workers와 GitHub Actions를 활용한 서버리스 라디오 예약 녹음 및 팟캐스트 송출 시스템입니다.

## 🏗️ 시스템 아키텍처 (Architecture)

이 시스템은 별도의 24시간 서버 없이, 스케줄링된 이벤트와 일회성 컴퓨팅 자원만을 사용하여 비용 효율적으로 동작합니다.

```mermaid
graph TD
    subgraph Cloudflare
        Cron[⏰ Cron Trigger] -->|1분 전 실행| Worker[⚡ Workers (trigger.js)]
        User[📱 사용자/팟캐스트 앱] -->|요청| Worker
    end

    subgraph GitHub ["GitHub (Private Repo)"]
        Worker -->|1. 녹음 시작 요청 (Dispatch)| Actions[🚀 GitHub Actions (Recording)]
        Worker -->|2. 파일 접근 (Proxy)| Raw[📦 Publish Branch (Raw Content)]
        
        Actions -->|3. 스트리밍 다운로드| Recorder[🎙️ recorder.py (FFmpeg)]
        Recorder -->|4. 파일 저장 & RSS 생성| Artifacts[💾 .m4a / feed.xml]
        Artifacts -->|5. 배포 (Push)| Raw
    end

    subgraph External
        EBS[📻 EBS 실시간 스트림] --> Recorder
    end
```

## 📂 디렉토리 구조

```
.
├── .github/workflows/
│   └── record.yml       # 녹음 및 배포 파이프라인 (GitHub Actions)
├── src/
│   ├── recorder.py      # 스트림 녹음 및 메타데이터 처리 (Python)
│   └── rss_gen.py       # 팟캐스트 RSS 피드 생성 (Python)
├── workers/
│   └── trigger.js       # 스케줄러 및 프록시 서버 (Cloudflare Workers)
├── wrangler.toml        # 통합 설정 파일 (스케줄, 프로그램 정보 등)
└── README.md
```

## ⚙️ 설정 방법 (Configuration)

모든 스케줄과 프로그램 설정은 `wrangler.toml` 파일 하나에서 관리합니다.

### 1. 스케줄 등록 (`SCHEDULE_JSON`)

`wrangler.toml` 파일 내 `SCHEDULE_JSON` 변수를 수정하여 프로그램을 등록합니다.

```toml
[vars]
SCHEDULE_JSON = '''
{
  "19:59": [  # UTC 시간 (KST 05:00 - 1분)
    {
      "program_name": "초급 일본어",
      "scheduled_time": "05:00:30",  # 녹음 시작 시간 (KST)
      "duration": 1110,              # 녹음 시간 (초)
      "days": [0, 1, 2]              # 요일 필터 (UTC 기준: 일,월,화)
    }
  ]
}
'''
```

### 2. 알람(Cron) 등록

Cloudflare 무료 플랜 제한을 피하기 위해 여러 시간대를 그룹화하여 등록합니다.

```toml
[triggers]
crons = ["59 19-21 * * SUN-FRI", ...] 
```

## 🎧 팟캐스트 주소

Cloudflare Worker 주소를 통해 팟캐스트 앱(Apple Podcasts 등)에 등록할 수 있습니다.

*   **URL 패턴**: `https://<당신의-워커-주소>/<프로그램명>/feed.xml`
*   **예시**: `https://ebs-record.sogeuni.workers.dev/초급-일본어/feed.xml`

## 🔒 보안 (Security)

*   **Private Repository**: 녹음 파일은 Private 저장소의 `publish` 브랜치에 저장됩니다.
*   **Secure Proxy**: Cloudflare Worker가 `GITHUB_TOKEN`을 사용하여 인증된 프록시 역할을 하므로, 외부에 토큰을 노출하지 않고도 파일에 접근할 수 있습니다.

## 🧹 브랜치 관리

*   **main**: 소스 코드 관리
*   **publish**: 녹음된 오디오 파일과 RSS 피드만 저장 (소스 코드 없음)
