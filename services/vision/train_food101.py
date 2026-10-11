import torch
from  transformers import pipeline
from transformers import AutoImageProcessor
from torchvision.transforms import RandomResizedCrop, Compose, Normalize, ToTensor
from transformers import DefaultDataCollator
import evaluate
import numpy as np
from transformers import AutoModelForImageClassification, TrainingArguments, Trainer


from datasets import load_dataset

item= load_dataset("ethz/food101", split="train[:5000]")

item= item.train_test_split(test_size=0.2)

labels = item["train"].features["label"].names

label2id = {}
id2label = {}

for i, label in enumerate(labels):
    label2id[label] = i
    id2label[i] = label



checkpoint = "google/vit-base-patch16-224-in21k"
image_processor = AutoImageProcessor.from_pretrained(checkpoint)

normalize = Normalize(mean=image_processor.image_mean, std=image_processor.image_std)
size = (
    image_processor.size["shortest_edge"]
    if "shortest_edge" in image_processor.size
    else (image_processor.size["height"], image_processor.size["width"])
)
_transforms = Compose([RandomResizedCrop(size), ToTensor(), normalize])

def transforms(examples):
    examples["pixel_values"] = [_transforms(img.convert("RGB")) for img in examples["image"]]
    del examples["image"]
    return examples


item= item.with_transform(transforms)
data_collator = DefaultDataCollator()

accuracy = evaluate.load("accuracy")

def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=1)
    return accuracy.compute(predictions=predictions, references=labels)


model = AutoModelForImageClassification.from_pretrained(
    checkpoint,
    num_labels=len(labels),
    id2label=id2label,
    label2id=label2id,
)


training_args = TrainingArguments(
    output_dir="my_awesome_food_model",
    remove_unused_columns=False,
    eval_strategy="epoch",
    save_strategy="epoch",
    learning_rate=5e-5,
    per_device_train_batch_size=16,
    gradient_accumulation_steps=4,
    per_device_eval_batch_size=16,
    num_train_epochs=3,
    warmup_steps=0.1,  # Transformers 5: a fraction means 10% of training steps.
    logging_steps=10,
    report_to="none",
    run_name="food101",
    load_best_model_at_end=True,
    metric_for_best_model="accuracy",
    push_to_hub=False,
)

trainer = Trainer(
    model=model,
    args=training_args,
    data_collator=data_collator,
    train_dataset=food["train"],
    eval_dataset=food["test"],
    processing_class=image_processor,
    compute_metrics=compute_metrics,
)

print("starting model training...")
trainer.train()

print("Training completed!")

results = trainer.evaluate()

print("Evaluation results:")
print(results)

trainer.save_model("./models/homepilot-vit")

print("Model saved successfully!")