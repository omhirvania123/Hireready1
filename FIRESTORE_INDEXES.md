# Firestore Indexes Setup

## Problem
The application was encountering Firestore index errors due to complex queries that require composite indexes.

## Solution
I've provided two solutions:

### Solution 1: Create Required Indexes (Recommended)

1. **Use the Firebase Console Link** (Easiest):
   - Click on the link provided in the error message:
   ```
   https://console.firebase.google.com/v1/r/project/ai-voice-interview-platform/firestore/indexes?create_composite=Cl5wcm9qZWN0cy9haS12b2ljZS1pbnRlcnZpZXctcGxhdGZvcm0vZGF0YWJhc2VzLyhkZWZhdWx0KS9jb2xsZWN0aW9uR3JvdXBzL2ludGVydmlld3MvaW5kZXhlcy9fEAEaDQoJZmluYWxpemVkEAEaDQoJY3JlYXRlZEF0EAIaCgoGdXNlcklkEAIaDAoIX19uYW1lX18QAg
   ```
   - This will automatically create the required composite index

2. **Deploy Indexes via Firebase CLI**:
   ```bash
   # Install Firebase CLI if not already installed
   npm install -g firebase-tools
   
   # Login to Firebase
   firebase login
   
   # Deploy the indexes
   firebase deploy --only firestore:indexes
   ```

### Solution 2: Code Modification (Already Applied)
I've modified the `getLatestInterviews` function in `lib/actions/general.action.ts` to avoid the complex index requirement by:
- Removing the `where("userId", "!=", userId)` filter from the Firestore query
- Filtering out the user's own interviews in the application code instead

## Required Indexes

### 1. Interviews Collection
- **Purpose**: Support queries for user interviews with ordering
- **Fields**: `userId` (ASC), `createdAt` (DESC)

### 2. Feedback Collection  
- **Purpose**: Support queries for feedback by interview and user
- **Fields**: `interviewId` (ASC), `userId` (ASC)

## Index Status
After creating the indexes, they will take a few minutes to build. You can monitor their status in the Firebase Console under Firestore > Indexes.

## Testing
Once the indexes are created and built, the application should work without the index errors.
