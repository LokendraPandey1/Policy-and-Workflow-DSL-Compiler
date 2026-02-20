// Academic Administration - Student Enrollment
// This example demonstrates policies and workflows for student enrollment processing

policy StudentEligibility {
    input gpa: number
    input credits: number
    input is_enrolled: boolean

    rule min_gpa: gpa >= 3.0
    rule min_credits: credits >= 30
    rule active: is_enrolled == true

    evaluate: min_gpa AND min_credits AND active
}

policy CoursePrerequisites {
    input math_score: number
    input english_score: number

    rule math_ready: math_score >= 70
    rule english_ready: english_score >= 65

    evaluate: math_ready AND english_ready
}

workflow EnrollmentProcess {
    step CheckEligibility {
        execute policy StudentEligibility
        on pass -> next
        on fail -> reject "Student does not meet eligibility requirements"
    }

    step VerifyPrerequisites {
        execute policy CoursePrerequisites
        on pass -> next
        on fail -> reject "Student does not meet course prerequisites"
    }

    step AssignCourses {
        action "Assign student to selected courses"
        on complete -> next
    }

    step NotifyStudent {
        action "Send enrollment confirmation email"
        on complete -> done
    }
}
