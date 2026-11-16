/** A backend-reported stage, never a time-based guess or percentage. */
export type PipelineStage =
  | 'UNKNOWN'
  | 'STARTING'
  | 'DOWNLOADING'
  | 'TRANSCRIBING'
  | 'READING_SCREEN'
  | 'SUMMARIZING'
  | 'FINALIZING'
  | 'COMPLETED'
  | 'FAILED';

export function pipelineStageCopy(stage: PipelineStage | undefined): {
  label: string;
  description: string;
} {
  switch (stage) {
    case 'STARTING':
      return { label: '분석 준비', description: '영상을 분석할 준비를 하고 있어요.' };
    case 'DOWNLOADING':
      return { label: '영상 정보 수집', description: '영상을 불러오고 있어요.' };
    case 'TRANSCRIBING':
      return { label: '음성 분석', description: '영상에서 말한 내용을 듣고 있어요.' };
    case 'READING_SCREEN':
      return { label: '화면 분석', description: '화면에 나타나는 정보를 확인하고 있어요.' };
    case 'SUMMARIZING':
      return { label: '핵심 내용 정리', description: '중요한 내용을 요약하고 분류하고 있어요.' };
    case 'FINALIZING':
      return { label: '저장 마무리', description: '분석 결과를 저장하고 있어요.' };
    case 'COMPLETED':
      return { label: '완료', description: '영상 정리가 끝났어요.' };
    case 'FAILED':
      return { label: '분석 실패', description: '정리를 완료하지 못했어요.' };
    default:
      return { label: '내용 분석', description: '영상 내용을 정리하고 있어요.' };
  }
}
