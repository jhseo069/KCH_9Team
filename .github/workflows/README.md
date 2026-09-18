# .github/workflows

## 폴더 목적/용도
GitHub Actions 자동 작업. GitHub이 이 폴더의 `.yml` 파일을 읽어 정해진 일정에 실행한다.

## 폴더 생성일
2026-09-18

## 폴더 내 규칙
- 워크플로 파일은 `.yml` 확장자. GitHub 규칙상 파일명은 영문(kebab-case)으로 둔다
- **예약 실행(schedule)은 `main` 브랜치에 있는 파일만 동작한다.** 다른 브랜치에 두면 아무 일도 일어나지 않는다
- 비밀정보는 워크플로에 넣지 않는다. 외부 서비스는 가능하면 우리 API를 거쳐 부른다(키는 Vercel에만 둔다)
- 그 외 산출물은 상위 [산출물 저장 규칙](../../../../CLAUDE.md#산출물-저장-규칙)을 따른다

**상위 `.github/` 폴더에는 README.md를 두지 않는다.** GitHub은 `.github/README.md`가 있으면
저장소 첫 화면에 프로젝트 루트의 `README.md` 대신 그것을 보여준다. 폴더 설명은 이 파일이 대신한다.

## 폴더 구성
- `supabase-keepalive.yml`: Supabase 무료 플랜 자동정지(7일 미사용) 방지. 월·목 12:00(KST)에
  `https://kch-9-team.vercel.app/api/site_judge?ping=1`을 호출해 실제 DB 조회를 1회 일으킨다.
  실패하면 job을 실패시켜 GitHub이 알림 메일을 보낸다. Actions 탭에서 수동 실행도 가능하다.

## 알아둘 점
- **공개 저장소는 60일간 커밋 등 활동이 없으면 GitHub이 예약 워크플로를 자동으로 끈다.**
  비공개 저장소는 해당 없다. 공개로 전환했다면 Actions 탭에서 가끔 상태를 확인할 것
- 이미 정지된 Supabase 프로젝트는 API 호출로 깨울 수 없다. 실패 알림을 받으면 Supabase
  대시보드에서 직접 `Restore project`를 눌러야 한다
