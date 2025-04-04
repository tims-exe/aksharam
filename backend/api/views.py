from django.shortcuts import render
from django.http import HttpResponse
from django.http import JsonResponse
from .models import Letters, Sentence, UserProgress, WordCategory, Word
import base64
from io import BytesIO
import cv2
import numpy as np
import os
import torch
from torchvision import transforms
from .ml_model.architecture import ConvNet
import pandas as pd
from django.contrib.auth.models import User
from .serializers import LetterSerializer, SentenceSerializer, UserProgressSerializer, UserSerializer, NoteSerializer, WordCategorySerializer, UserSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Note
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont
# from ocr_model.nllb_translator import translate_malayalam_to_english
from transformers import pipeline
from surya.recognition import RecognitionPredictor
from surya.detection import DetectionPredictor
import base64
from google.cloud import translate_v2 as translate
from rest_framework_simplejwt.tokens import RefreshToken


# Create your views here.


csv_path = os.path.join(os.path.dirname(__file__), "ml_model", "label_2_letter.csv")
csv_path_s = os.path.join(os.path.dirname(__file__), "ml_model", "label_2_symbol.csv")

class_labels_df = pd.read_csv(csv_path)
class_labels_df_s = pd.read_csv(csv_path_s)

class_mapping = dict(zip(class_labels_df["Image Name"], class_labels_df["Class Label"]))
class_mapping_s = dict(zip(class_labels_df_s["Image Name"], class_labels_df_s["Class Label"]))

MODEL_PATH = os.path.join(os.path.dirname(__file__), "ml_model", "mal_model.pth")
MODEL_PATH_S = os.path.join(os.path.dirname(__file__), "ml_model", "mal_model_symbols.pth")

# csv_path = os.path.join(os.path.dirname(__file__), "ml_model", "label_2_letter2.csv")
# class_labels_df = pd.read_csv(csv_path)
# class_mapping = dict(zip(class_labels_df["Image Name"], class_labels_df["Class Label"]))

# MODEL_PATH = os.path.join(os.path.dirname(__file__), "ml_model", "mal_model_chil.pth")


@api_view(['GET'])
@permission_classes([AllowAny])
def test(request):
    return JsonResponse({"message": "Aksharam"})


def get_word_categories(request):
    words = Word.objects.select_related('word_category').values(
        'id', 'word', 'english_version', 'word_translation', 'category_id', 'category'
    )  
    return JsonResponse({"Words": list(words)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_data(request):
    user = request.user  
    serializer = UserSerializer(user)
    data = serializer.data
    data.pop("password", None)
    return Response(data)


@api_view(["POST"]) 
@permission_classes([IsAuthenticated])
def main_canvas(request):
    try:
        image_data = request.data.get("image", "")
        category = request.data.get("category", "main")  # Default to "main" if not provided

        if not image_data.startswith("data:image/png;base64,"):
            return JsonResponse({"message": "Invalid image format"}, status=status.HTTP_400_BAD_REQUEST)
        
        print('got image')

        # Decode base64 image
        image_data = image_data.split(",")[1]
        image_bytes = base64.b64decode(image_data)
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        # Convert BGR to RGB (if needed)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image_pil = Image.fromarray(image_rgb)

        if image_pil is None:
            return JsonResponse({"message": "Error decoding image"}, status=status.HTTP_400_BAD_REQUEST)

        raw_transform = transforms.Compose([
            transforms.Resize((32, 32)),                    
            transforms.ToTensor(),                          
        ])

        print(category)

        num = 49

        # Determine model and class mapping based on category
        if category == "symbol":
            print("Using symbol model")
            model_path = MODEL_PATH_S
            print("model")

            if not os.path.exists(MODEL_PATH_S):
                raise FileNotFoundError(f"Error: Model file not found at {MODEL_PATH_S}")

            if class_mapping_s is None:
                raise ValueError("Error: class_mapping2 is None!")

            print(f"Class Mapping 2 Keys: {list(class_mapping_s.keys())}")  # Debug
            cm = class_mapping_s

            num = 11

        else :
            print("Using main model")
            model_path = MODEL_PATH

            if not os.path.exists(MODEL_PATH):
                raise FileNotFoundError(f"Error: Model file not found at {MODEL_PATH}")

            if class_mapping is None:
                raise ValueError("Error: class_mapping2 is None!")

            print(f"Class Mapping 2 Keys: {list(class_mapping.keys())}")  # Debug

            cm = class_mapping

            num = 49
        
        # Load the model
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = ConvNet(num_classes=num).to(device)
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.eval()

        transformed_image = raw_transform(image_pil)
        transformed_image = transformed_image.unsqueeze(0).to(device)

        # Perform inference
        with torch.no_grad():
            output = model(transformed_image)
            _, predicted = torch.max(output, 1)
            predicted_class = predicted.item()

        predicted_label = cm.get(predicted_class, "Unknown")

        return JsonResponse({"predicted_label": predicted_label}, status=status.HTTP_200_OK)

    except Exception as e:
        return JsonResponse({"message": f"Error processing image: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_letters(request):
    try:
        letters = Letters.objects.all() 
        serializer = LetterSerializer(letters, many=True) 
        return Response(serializer.data, status=status.HTTP_200_OK)  
    except Letters.DoesNotExist:
        return Response({"message": "No letters found."}, status=status.HTTP_404_NOT_FOUND)
    
# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def get_all_words(request):
#     words = Word.objects.select_related('word_category').values(
#         'id', 'word', 'english_version', 'word_translation', 'category_id', 'category'
#     )  
#     return JsonResponse({"Words": list(words)})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_words(request):
    categories = WordCategory.objects.prefetch_related('words').all()
    serializer = WordCategorySerializer(categories, many=True)
    return Response({"Words": serializer.data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_sentences(request):
    sentences = Sentence.objects.all()
    serializer = SentenceSerializer(sentences, many=True)
    return Response({"Sentences": serializer.data})


def extract_malayalam_text(image_file):
    original_image = Image.open(image_file)
    
    langs = ["ml"]
    
    recognition_predictor = RecognitionPredictor()
    detection_predictor = DetectionPredictor()
    
    predictions = recognition_predictor([original_image], [langs], detection_predictor)
    
    text_lines = predictions[0].text_lines
    
    extracted_text = "\n".join([line.text for line in text_lines])
    
    draw_image = original_image.copy()
    draw = ImageDraw.Draw(draw_image)

    try:
        font = ImageFont.load_default()
    except Exception as e:
        print(f"Could not load default font: {e}")
        font = None

    for line in text_lines:
        polygon = line.polygon
        draw.polygon([(p[0], p[1]) for p in polygon], outline='red', width=3)
        
        # if font:
        #     text = line.text
        #     text_position = (int(polygon[0][0]), int(polygon[0][1] - 25))
        #     # draw.text(text_position, text, fill='blue')

    return extracted_text, draw_image

# def translate_malayalam_to_english(text):
#     # Load the translation pipeline
#     print("Loading translator...")
#     translator = pipeline("translation", model="facebook/nllb-200-distilled-1.3B")
#     print("loaded translator")
#     translations = {}
    
#     if '\\n' in text:
#         processed_text = text.replace('\\n', '\n')
#     else:
#         processed_text = text
    
#     full_text_for_translation = processed_text.replace('\n', ' ')
#     full_result = translator(full_text_for_translation, src_lang="mal_Mlym", tgt_lang="eng_Latn")
#     translations['full'] = full_result[0]['translation_text']
    
#     lines = processed_text.split('\n')
#     lines = [line for line in lines if line.strip()]
    
#     for i, line in enumerate(lines):
#         if line.strip():  # Skip empty lines
#             line_result = translator(line, src_lang="mal_Mlym", tgt_lang="eng_Latn")
#             translations[line] = line_result[0]['translation_text']
#     print("translation done")
#     return translations

import html
from google.cloud import translate_v2 as translate

def translate_malayalam_to_english(text):
    # Initialize the Google Translate client
    client = translate.Client()

    # Prepare the translation dictionary
    translations = {}

    # Handle newline replacements
    processed_text = text.replace('\\n', '\n') if '\\n' in text else text

    # Full text translation
    full_text_for_translation = processed_text.replace('\n', ' ')

    # Translate the entire text
    full_result = client.translate(full_text_for_translation, source_language='ml', target_language='en')
    translations['full'] = html.unescape(full_result['translatedText'])  # Fix HTML encoding

    # Translate line by line
    lines = [line.strip() for line in processed_text.split('\n') if line.strip()]

    for line in lines:
        line_result = client.translate(line, source_language='ml', target_language='en')
        translations[line] = html.unescape(line_result['translatedText'])  # Fix HTML encoding

    print("Translation done")
    return translations


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def scan_image(request):
    if request.method == 'POST' and request.FILES.get('image'):
        image_file = request.FILES['image']

        try:
            # Assuming extract_malayalam_text returns a tuple (malayalam_text, boxed_image)
            malayalam_text, boxed_image = extract_malayalam_text(image_file)
            print("got extracted text:", malayalam_text)
            
            # Translate the text to English
            translated_text = translate_malayalam_to_english(malayalam_text)
            print("Translated text:", translated_text)

            # Convert boxed image to base64
            image_buffer = BytesIO()
            boxed_image.save(image_buffer, format="JPEG")
            image_buffer.seek(0)  # Important to seek to the start of the image buffer
            image_base64 = base64.b64encode(image_buffer.read()).decode('utf-8')

            response_data = {
                'translated_text': translated_text,
                'boxed_image': f'data:image/jpeg;base64,{image_base64}'
            }
            return JsonResponse(response_data)
        
        except Exception as e:
            print("Error during image processing:", e)
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)



@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def note_list_create(request):
    if request.method == 'GET':
        notes = Note.objects.filter(author=request.user)
        serializer = NoteSerializer(notes, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = NoteSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(author=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Delete a Note
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def note_delete(request, pk):
    try:
        note = Note.objects.get(pk=pk, author=request.user)
    except Note.DoesNotExist:
        return Response({'error': 'Note not found'}, status=status.HTTP_404_NOT_FOUND)

    note.delete()
    return Response({'message': 'Note deleted successfully'}, status=status.HTTP_204_NO_CONTENT)

@api_view(['POST'])
@permission_classes([AllowAny])
def create_user(request):
    # Check if the username already exists
    username = request.data.get('username')
    if User.objects.filter(username=username).exists():
        print('user exists')
        return Response({"detail": "invalid_username"}, status=status.HTTP_400_BAD_REQUEST)
    
    # If the username doesn't exist, proceed with the serializer
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        # Save the user object
        user = serializer.save()
        # Create a new UserProgress record for the new user
        UserProgress.objects.create(user=user)
        
        # Generate tokens for the newly created user
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        
        # Return both the user data and tokens
        response_data = {
            'user': serializer.data,
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def get_user_progress(request):
    
#     user = request.user  # Get the logged-in user
#     try:
#         progress = UserProgress.objects.get(user=user)  # Fetch progress for the user
#         serializer = UserProgressSerializer(progress)  # Serialize the data
#         return Response(serializer.data)  # Send as JSON response
#     except UserProgress.DoesNotExist:
#         print("error")
#         return Response({'message': 'No progress found for this user'}, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_progress(request):
    user = request.user  # Get the logged-in user
    try:
        progress = UserProgress.objects.get(user=user)  # Fetch progress for the user
        completed_letters = [letter.letter for letter in progress.completed_letters.all()]  # Get all completed letters
        completed_words = [word.word for word in progress.completed_words.all()]  # Get all completed words
        completed_sentences = [sentence.sentence for sentence in progress.completed_sentences.all()]  # Get all completed sentences
        
        return Response({
            'completed_letters': completed_letters,
            'completed_words': completed_words,
            'completed_sentences': completed_sentences
        })
    except UserProgress.DoesNotExist:
        return Response({'message': 'No progress found for this user'}, status=404)
    

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_user_progress(request):
    # Get the logged-in user
    user = request.user

    print(user)

    try:
        # Fetch the UserProgress instance for the current user
        progress = UserProgress.objects.get(user=user)

        # Check which field is being updated and update accordingly
        if 'completed_letters' in request.data:
            completed_letters = request.data.get('completed_letters', [])
            for letter in completed_letters:
                try:
                    letter_instance = Letters.objects.get(letter=letter)
                    progress.completed_letters.add(letter_instance)
                except Letters.DoesNotExist:
                    return Response({'message': f'Letter {letter} not found'}, status=400)

        if 'completed_words' in request.data:
            completed_words = request.data.get('completed_words', [])
            for word in completed_words:
                try:
                    word_instance = Word.objects.get(word=word)
                    progress.completed_words.add(word_instance)
                except Word.DoesNotExist:
                    return Response({'message': f'Word {word} not found'}, status=400)

        if 'completed_sentences' in request.data:
            completed_sentences = request.data.get('completed_sentences', [])
            for sentence in completed_sentences:
                try:
                    sentence_instance = Sentence.objects.get(sentence=sentence)
                    progress.completed_sentences.add(sentence_instance)
                except Sentence.DoesNotExist:
                    return Response({'message': f'Sentence {sentence} not found'}, status=400)

        # Save the updated progress
        progress.save()

        # Serialize the updated UserProgress and return the response
        serializer = UserProgressSerializer(progress)
        return Response(serializer.data, status=200)

    except UserProgress.DoesNotExist:
        return Response({'message': 'No progress found for this user'}, status=404)




# @api_view(["POST"])
# @permission_classes([IsAuthenticated])
# def main_canvas(request):
#     try:
#         image_data = request.data.get("image", "")
#         if not image_data.startswith("data:image/png;base64,"):
#             print("Invalid image format")
#             return JsonResponse({"message": "Invalid image format"}, status=status.HTTP_400_BAD_REQUEST)
        
#         print("Got image, decoding now...")
        
#         # Decode base64 image
#         image_data = image_data.split(",")[1]
#         image_bytes = base64.b64decode(image_data)
#         image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        
#         print("Image array shape:", image_array.shape)
        
#         image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
#         if image is None:
#             print("Error decoding image")
#             return JsonResponse({"message": "Error decoding image"}, status=status.HTTP_400_BAD_REQUEST)
        
#         print("Image successfully decoded")
        
#         # Convert BGR to RGB
#         image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
#         image_pil = Image.fromarray(image_rgb)

#         # Check PIL image
#         if image_pil is None:
#             print("Error converting to PIL Image")
#             return JsonResponse({"message": "Error converting image"}, status=status.HTTP_400_BAD_REQUEST)
        
#         print("Image successfully converted to PIL")
        
#         raw_transform = transforms.Compose([
#             transforms.Resize((32, 32)),                    
#             transforms.ToTensor(),                          
#         ])

#         # Load model with num_classes=6
#         device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
#         model = ConvNet(num_classes=5).to(device)
        
#         print("Loading model...")
#         model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
#         model.eval()
#         print("Model loaded successfully")

#         transformed_image = raw_transform(image_pil).unsqueeze(0).to(device)
#         print("Image transformed and moved to device")

#         # Run inference
#         with torch.no_grad():
#             output = model(transformed_image)
#             _, predicted = torch.max(output, 1)
#             predicted_class = predicted.item()
        
#         print("Predicted class:", predicted_class)
        
#         predicted_label = class_mapping.get(predicted_class, "Unknown")
#         print("Predicted label:", predicted_label)

#         return JsonResponse({"predicted_label": predicted_label}, status=status.HTTP_200_OK)

#     except Exception as e:
#         print("Error processing image:", str(e))
#         return JsonResponse({"message": f"Error processing image: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

