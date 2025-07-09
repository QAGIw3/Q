// WebAppQ/app/src/components/common/FeedbackBox.test.tsx
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { FeedbackBox } from './FeedbackBox';
import * as h2mAPI from '../../services/h2mAPI';

// Mock the h2mAPI module
jest.mock('../../services/h2mAPI');
const mockedH2mAPI = h2mAPI as jest.Mocked<typeof h2mAPI>;

describe('FeedbackBox', () => {
  const props = {
    reference_id: 'summary123',
    context: 'AISummary',
    prompt: 'what is the Q platform?',
  };

  it('renders the initial state correctly', () => {
    render(<FeedbackBox {...props} />);
    expect(screen.getByText('Was this helpful?')).toBeInTheDocument();
    expect(screen.getByTitle('Helpful')).toBeInTheDocument();
    expect(screen.getByTitle('Not Helpful')).toBeInTheDocument();
  });

  it('calls submitFeedback with a positive score when thumbs up is clicked', async () => {
    mockedH2mAPI.submitFeedback.mockResolvedValue(); // Mock a successful submission
    render(<FeedbackBox {...props} />);
    
    const helpfulButton = screen.getByTitle('Helpful');
    fireEvent.click(helpfulButton);
    
    await waitFor(() => {
      expect(mockedH2mAPI.submitFeedback).toHaveBeenCalledTimes(1);
      expect(mockedH2mAPI.submitFeedback).toHaveBeenCalledWith({
        reference_id: props.reference_id,
        context: props.context,
        prompt: props.prompt,
        score: 1,
      });
    });
  });

  it('shows a "Thank you" message after successful submission', async () => {
    mockedH2mAPI.submitFeedback.mockResolvedValue();
    render(<FeedbackBox {...props} />);
    
    fireEvent.click(screen.getByTitle('Helpful'));
    
    await waitFor(() => {
      expect(screen.getByText('Thank you for your feedback!')).toBeInTheDocument();
    });
    
    expect(screen.queryByText('Was this helpful?')).not.toBeInTheDocument();
  });

  it('shows an error message if the submission fails', async () => {
    const errorMessage = 'Failed to submit feedback.';
    mockedH2mAPI.submitFeedback.mockRejectedValue(new Error(errorMessage));
    render(<FeedbackBox {...props} />);

    fireEvent.click(screen.getByTitle('Helpful'));

    await waitFor(() => {
        expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });
  });
}); 