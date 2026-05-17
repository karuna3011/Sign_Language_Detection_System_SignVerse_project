# utils/gesture_words.py
# Maps detected gesture labels to meaningful words/sentences

GESTURE_TO_WORD = {
    # ASL Alphabet mapped to common words/sentences
    'A': 'Hello',
    'B': 'Goodbye',
    'C': 'Come here',
    'D': 'Done',
    'E': 'Excuse me',
    'F': 'Fine, thank you',
    'G': 'Good morning',
    'H': 'How are you?',
    'I': 'I am okay',
    'J': 'Just a moment',
    'K': 'Keep going',
    'L': 'Love you',
    'M': 'My name is...',
    'N': 'No',
    'O': 'Okay',
    'P': 'Please',
    'Q': 'Quiet please',
    'R': 'Right',
    'S': 'Sorry',
    'T': 'Thank you',
    'U': 'Understand',
    'V': 'Very good',
    'W': 'Wait please',
    'X': 'Not correct',
    'Y': 'Yes',
    'Z': 'Zero',

    # Common gestures mapped to sentences
    'THUMBS_UP':   'Great job!',
    'THUMBS_DOWN': 'I disagree',
    'PEACE':       'Peace and love',
    'OPEN_HAND':   'Stop please',
    'FIST':        'I need help',
    'POINTING':    'Look over there',

    # Fallback
    'UNKNOWN':     'Gesture not recognized',
}


def get_word_for_gesture(gesture_label):
    """
    Returns the word/sentence for a given gesture label.
    Falls back to the label itself if not found.
    """
    return GESTURE_TO_WORD.get(gesture_label, gesture_label)


def get_all_gesture_words():
    """
    Returns the full mapping dictionary.
    """
    return GESTURE_TO_WORD