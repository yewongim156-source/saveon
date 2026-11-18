/** Only stages supported by the existing Spring Content API are surfaced. */
export type AnalysisProgressStatus =
  | 'SUBMITTING' // local client request in flight
  | 'UPLOADING'  // local multipart request in flight
  | 'PENDING'    // server accepted, waiting for the worker
  | 'ANALYZING'  // server is analyzing; internal STT/OCR stages unavailable
  | 'COMPLETED'
  | 'FAILED';

export type StageTone = 'active' | 'complete' | 'waiting' | 'failed';

export function activeStage(status: AnalysisProgressStatus): number {
  if (status === 'SUBMITTING' || status === 'UPLOADING') return 0;
  if (status === 'PENDING' || status === 'ANALYZING') return 1;
  return 2;
}

export function stageTone(status: AnalysisProgressStatus, index: number): StageTone {
  const current = activeStage(status);
  if (index < current) return 'complete';
  if (index > current) return 'waiting';
  if (status === 'COMPLETED') return 'complete';
  if (status === 'FAILED') return 'failed';
  return 'active';
}

export function progressCopy(status: AnalysisProgressStatus): {
  heading: string;
  description: string;
} {
  switch (status) {
    case 'SUBMITTING':
      return { heading: '링크를 저장하고 있어요', description: '저장 요청을 보내고 있어요.' };
    case 'UPLOADING':
      return { heading: '영상을 전송하고 있어요', description: '선택한 영상을 서버로 보내는 중이에요.' };
    case 'PENDING':
      return { heading: '정리할 차례를 기다리고 있어요', description: '저장은 완료됐어요. 잠시 후 내용을 정리할게요.' };
    case 'ANALYZING':
      return { heading: '영상 내용을 정리하고 있어요', description: '분석이 진행 중이에요. 다른 화면을 이용해도 괜찮아요.' };
    case 'COMPLETED':
      return { heading: '영상 정리가 끝났어요', description: '정리된 내용을 저장물에서 확인할 수 있어요.' };
    case 'FAILED':
      return { heading: '영상 정리를 완료하지 못했어요', description: '저장물에서 상태를 확인하고 다시 시도할 수 있어요.' };
  }
}
