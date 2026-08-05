/**
 * QuizPanel 组件测试。
 */

import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QuizPanel, type QuizQuestion } from "./QuizPanel";

// ============================================================================
// Helpers
// ============================================================================

function makeMCQuestions(n: number = 3): QuizQuestion[] {
  return Array.from({ length: n }, (_, i) => ({
    id: `q${i + 1}`,
    type: "multiple_choice" as const,
    question: `Question ${i + 1}?`,
    options: [
      { id: "a", text: `Option A${i}`, is_correct: i === 0 },
      { id: "b", text: `Option B${i}`, is_correct: i === 1 },
      { id: "c", text: `Option C${i}` },
      { id: "d", text: `Option D${i}` },
    ],
    explanation: `Explanation ${i + 1}`,
    difficulty: (i % 3) + 1 as 1 | 2 | 3,
    related_concept: "c1",
  }));
}

function makeTFQuestion(): QuizQuestion {
  return {
    id: "tf1", type: "true_false",
    question: "Is the sky blue?",
    correct_answer: "true", explanation: "Yes.",
    difficulty: 1,
  };
}

// ============================================================================
// Tests
// ============================================================================

describe("QuizPanel", () => {
  it("renders question text", () => {
    render(<QuizPanel questions={makeMCQuestions(1)} />);
    expect(screen.getByText("Question 1?")).toBeInTheDocument();
  });

  it("renders empty state when no questions", () => {
    render(<QuizPanel questions={[]} />);
    expect(screen.getByText("暂无练习题")).toBeInTheDocument();
  });

  it("shows progress indicator", () => {
    render(<QuizPanel questions={makeMCQuestions(3)} />);
    expect(screen.getByText("1 / 3")).toBeInTheDocument();
  });

  it("shows difficulty badge", () => {
    render(<QuizPanel questions={makeMCQuestions(1)} />);
    expect(screen.getByText("入门")).toBeInTheDocument();
  });

  it("shows question type badge", () => {
    render(<QuizPanel questions={makeMCQuestions(1)} />);
    expect(screen.getByText("选择题")).toBeInTheDocument();
  });

  it("renders all options for multiple choice", () => {
    render(<QuizPanel questions={makeMCQuestions(1)} />);
    expect(screen.getByText("Option A0")).toBeInTheDocument();
    expect(screen.getByText("Option B0")).toBeInTheDocument();
    expect(screen.getByText("Option C0")).toBeInTheDocument();
    expect(screen.getByText("Option D0")).toBeInTheDocument();
  });

  it("selects option on click", () => {
    const q = makeMCQuestions(1);
    // Make option B the correct one for clear testing
    q[0] = {
      ...q[0],
      options: [
        { id: "a", text: "Wrong", is_correct: false },
        { id: "b", text: "Correct", is_correct: true },
        { id: "c", text: "Also Wrong" },
      ],
    };
    render(<QuizPanel questions={q} />);

    const wrongOption = screen.getByText("Wrong").closest("button")!;
    fireEvent.click(wrongOption);

    // Should show feedback area
    expect(screen.getByText(/回答错误/)).toBeInTheDocument();
  });

  it("shows correct feedback for right answer", () => {
    const q = makeMCQuestions(1);
    q[0] = {
      ...q[0],
      options: [
        { id: "a", text: "Correct One", is_correct: true },
        { id: "b", text: "Wrong One" },
      ],
    };
    render(<QuizPanel questions={q} />);

    const correctOption = screen.getByText("Correct One").closest("button")!;
    fireEvent.click(correctOption);

    expect(screen.getByText(/回答正确/)).toBeInTheDocument();
  });

  it("shows explanation on reveal", () => {
    const q = makeMCQuestions(1);
    q[0] = {
      ...q[0], explanation: "This is the detailed explanation.",
    };
    render(<QuizPanel questions={q} />);

    // Click the first correct option (index 0 = "Option A0" which is_correct for i=0)
    fireEvent.click(screen.getByText("Option A0").closest("button")!);
    fireEvent.click(screen.getByText("查看解析"));

    expect(screen.getByText("This is the detailed explanation.")).toBeInTheDocument();
  });

  it("navigates to next question", () => {
    render(<QuizPanel questions={makeMCQuestions(3)} />);

    // Answer current question by clicking the correct option (first option in makeMCQuestions)
    const firstOption = screen.getByText("Option A0").closest("button")!;
    fireEvent.click(firstOption);

    // Find and click next button
    const nextButton = screen.getByText(/下一题/).closest("button")!;
    fireEvent.click(nextButton);

    // Should show second question
    expect(screen.getByText("2 / 3")).toBeInTheDocument();
    expect(screen.getByText("Question 2?")).toBeInTheDocument();
  });

  it("shows completion screen after last question", () => {
    render(<QuizPanel questions={makeMCQuestions(1)} />);
    const q = makeMCQuestions(1);
    q[0] = {
      ...q[0],
      options: [
        { id: "a", text: "A", is_correct: true },
        { id: "b", text: "B" },
      ],
    };
    // Re-render is not needed; the mock data has correct option at index 0
    // which matches "Option A0"

    // Just answer and go to next (which shows completion since only 1 question)
    // Actually need to use the rendered component
    const option = screen.getByText("Option A0").closest("button")!;
    fireEvent.click(option);

    const viewResult = screen.getByText(/查看结果/).closest("button")!;
    fireEvent.click(viewResult);

    expect(screen.getByText("练习完成！")).toBeInTheDocument();
    expect(screen.getByText(/重新开始/)).toBeInTheDocument();
  });

  it("restart resets quiz", () => {
    render(<QuizPanel questions={makeMCQuestions(1)} />);

    const option = screen.getByText("Option A0").closest("button")!;
    fireEvent.click(option);
    fireEvent.click(screen.getByText(/查看结果/).closest("button")!);
    fireEvent.click(screen.getByText(/重新开始/).closest("button")!);

    // Back to first question
    expect(screen.getByText("1 / 1")).toBeInTheDocument();
    expect(screen.getByText("Question 1?")).toBeInTheDocument();
  });

  it("renders true/false question with correct buttons", () => {
    render(<QuizPanel questions={[makeTFQuestion()]} />);

    expect(screen.getByText(/正确/)).toBeInTheDocument();
    expect(screen.getByText(/错误/)).toBeInTheDocument();
  });

  it("true_false: selecting correct answer shows feedback", () => {
    render(<QuizPanel questions={[makeTFQuestion()]} />);

    fireEvent.click(screen.getByText(/正确/));
    expect(screen.getByText(/回答正确/)).toBeInTheDocument();
  });

  it("disables options after answering", () => {
    render(<QuizPanel questions={makeMCQuestions(1)} />);

    const option = screen.getByText("Option A0").closest("button")!;
    fireEvent.click(option);

    // All options should be disabled now
    const buttons = screen.getAllByRole("button").filter(
      (b) => b.textContent?.includes("Option")
    );
    for (const btn of buttons) {
      expect(btn).toBeDisabled();
    }
  });

  it("renders short_answer type with textarea", () => {
    const q: QuizQuestion[] = [{
      id: "sa1", type: "short_answer",
      question: "Explain the concept.", explanation: "Answer.",
      expected_keywords: ["keyword1", "keyword2"],
      difficulty: 3,
    }];
    render(<QuizPanel questions={q} />);

    expect(screen.getByPlaceholderText("请输入你的答案...")).toBeInTheDocument();
    expect(screen.getByText("简答题")).toBeInTheDocument();
  });
});
