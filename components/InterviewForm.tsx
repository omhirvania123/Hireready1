"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

const interviewFormSchema = z.object({
  role: z.string().min(1, "Role is required"),
  technology: z.string().min(1, "Technology is required"),
  difficultyLevel: z.enum(["Junior", "Mid", "Senior"], {
    required_error: "Please select a difficulty level",
  }),
  numberOfQuestions: z
    .number()
    .min(1, "At least 1 question is required")
    .max(50, "Maximum 50 questions allowed"),
  interviewType: z.enum(["Technical", "Behavioral", "Mixed"], {
    required_error: "Please select an interview type",
  }),
});

type InterviewFormValues = z.infer<typeof interviewFormSchema>;

interface InterviewFormProps {
  userId: string;
}

const InterviewForm = ({ userId }: InterviewFormProps) => {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const form = useForm<InterviewFormValues>({
    resolver: zodResolver(interviewFormSchema),
    defaultValues: {
      role: "",
      technology: "",
      difficultyLevel: undefined,
      numberOfQuestions: 5,
      interviewType: undefined,
    },
  });

  const onSubmit = async (data: InterviewFormValues) => {
    setIsSubmitting(true);
    setError(null);

    try {
      const response = await fetch("/api/vapi/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          role: data.role,
          level: data.difficultyLevel,
          techstack: data.technology,
          amount: data.numberOfQuestions,
          type: data.interviewType,
          userid: userId,
        }),
      });

      const result = await response.json();

      if (!response.ok || !result.success) {
        throw new Error(result.error || "Failed to create interview");
      }

      // Redirect to home/dashboard after creating interview
      router.push("/home");
      router.refresh();
    } catch (err: any) {
      setError(err.message || "Something went wrong. Please try again.");
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="card-border p-8">
        <h2 className="text-2xl font-bold mb-6">Schedule Your Interview</h2>
        <p className="text-muted-foreground mb-6">
          Fill out the form below to create a customized interview based on your
          preferences.
        </p>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            {/* Role Field */}
            <FormField
              control={form.control}
              name="role"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Job Role</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="e.g., Frontend Developer, Full Stack Developer"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>
                    Enter the job role you want to practice for
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Technology Field */}
            <FormField
              control={form.control}
              name="technology"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Technology / Tech Stack</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="e.g., React, Node.js, Python (comma-separated)"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>
                    Enter technologies separated by commas (e.g., React, TypeScript,
                    Next.js)
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Difficulty Level */}
            <FormField
              control={form.control}
              name="difficultyLevel"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Difficulty Level</FormLabel>
                  <FormControl>
                    <select
                      {...field}
                      className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-xs transition-[color,box-shadow] outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50 md:text-sm"
                    >
                      <option value="">Select difficulty level</option>
                      <option value="Junior">Junior</option>
                      <option value="Mid">Mid</option>
                      <option value="Senior">Senior</option>
                    </select>
                  </FormControl>
                  <FormDescription>
                    Select your experience level
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Interview Type */}
            <FormField
              control={form.control}
              name="interviewType"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Interview Type</FormLabel>
                  <FormControl>
                    <select
                      {...field}
                      className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-xs transition-[color,box-shadow] outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50 md:text-sm"
                    >
                      <option value="">Select interview type</option>
                      <option value="Technical">Technical</option>
                      <option value="Behavioral">Behavioral</option>
                      <option value="Mixed">Mixed</option>
                    </select>
                  </FormControl>
                  <FormDescription>
                    Choose the type of interview questions
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Number of Questions */}
            <FormField
              control={form.control}
              name="numberOfQuestions"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Number of Questions</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      min={1}
                      max={50}
                      {...field}
                      onChange={(e) => {
                        if(e.target.value === "") {
                          field.onChange(0);
                          return;
                        }
                        field.onChange(parseInt(e.target.value))
                      }}
                    />
                  </FormControl>
                  <FormDescription>
                    How many questions would you like? (1-50)
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {error && (
              <div className="p-4 rounded-md bg-destructive/10 border border-destructive/20">
                <p className="text-sm text-destructive">{error}</p>
              </div>
            )}

            <Button
              type="submit"
              className="w-full btn-primary"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Creating Interview..." : "Schedule Interview"}
            </Button>
          </form>
        </Form>
      </div>
    </div>
  );
};

export default InterviewForm;