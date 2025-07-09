export interface FeedbackEvent {
    reference_id: string;
    context: string;
    score: number;
    prompt?: string;
    feedback_text?: string;
    model_version?: string;
} 