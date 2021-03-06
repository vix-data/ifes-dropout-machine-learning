# License: BSD 3 clause <https://opensource.org/licenses/BSD-3-Clause>
# Copyright (c) 2016, Fabricio Vargas Matos <fabriciovargasmatos@gmail.com>
# All rights reserved.

'''
Project: IFES dropout prediction

Use Machine Learning techniques to model a student's dropout prediction system for Brazilian Federal Institutes of Education, Science and Technology analyzing data available in the Q-Academico information system.
'''

# Load libraries
import os
import time
import pandas
import numpy
import matplotlib.pyplot as plt
from pandas.tools.plotting import scatter_matrix
from pandas import DataFrame
from sklearn.preprocessing import StandardScaler
from sklearn.preprocessing import MinMaxScaler
from sklearn import cross_validation
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.decomposition import PCA
from sklearn.externals import joblib
from sklearn.metrics import classification_report
from sklearn.metrics import confusion_matrix
from sklearn.metrics import accuracy_score

#constants
N_DIGITS = 3
NUM_FOLDS = 10
RAND_SEED = 7
SCORING = 'accuracy'
VALIDATION_SIZE = 0.20

#global variables
start = time.clock()
imageidx = 1
createImages = True
results = []
names = []
params = []

#load Dataframe from file/url
def loadDataframe(filename):
    return pandas.read_csv(filename, header=0, sep=';')

#drop not interesting columns and fill NaN values
def dataCleansing(dataframe):
    #axis: 0 for rows and 1 for columns
    dataframe.drop('hash_cod_matricula', axis=1, inplace=True)
    dataframe.drop('cep', axis=1, inplace=True)
    dataframe.drop('desc_curso', axis=1, inplace=True)

    #replace NaN with 0
    dataframe.fillna(value=0, inplace=True)
    
    return dataframe

# Split-out validation dataset
def splitoutValidationDataset(dataframe):    
    ncolumns = dataframe.shape[1]
    array = dataframe.values
    
    X = array[:,0:ncolumns-1].astype(float)
    Y = array[:,ncolumns-1]

    X_train, X_validation, Y_train, Y_validation = cross_validation.train_test_split(X, Y, test_size=VALIDATION_SIZE, random_state=RAND_SEED)

    return (X_train, X_validation, Y_train, Y_validation)

def rescaleData(X):
    pipeline = Pipeline([('MinMaxScaler', MinMaxScaler(feature_range=(0, 1))),('Scaler', StandardScaler())])

    scaler = pipeline.fit(X)
    rescaledX = scaler.transform(X)

    return rescaledX

    
def trainAndSaveLRModel(X_train, Y_train, outputFileNameForModel):
    print '\nTraining ...'

    rescaledX = rescaleData(X_train)

    # From the EDA4 we found:
    # Best: 0.853451 using {'max_features': 'log2', 'n_estimators': 1000, 'criterion': 'gini'}    
    model = RandomForestClassifier(max_features='log2', n_estimators=1000, criterion='gini')
    
    #train
    model.fit(rescaledX, Y_train)
    
    #save the trained model to file
    joblib.dump(model, outputFileNameForModel)
    print 'Model saved to "%s"' % outputFileNameForModel
    
    return model


def predictFromFile(modelFileName, inputFileName, outputFileName, inputHasTrainedData):
    # Load dataset
    dataframe = loadDataframe(inputFileName)

    # extract a matrix with the first column (student ID)
    X_objectIDs = dataframe.values[:,0:1]    
    '''
    [['0x002E7963AB8B4E0DC2A73FBD0916783A05BC54B2']
     ['0x00A6E19710B815EB9CD28DA63393D50D215D8C14']
     ['0x023AF122E0EAF0F437DB18D67E89EFC607002F25']
     (...)
     ['0x02BE59FF1EA063895E2DFFCAF894197B87A7CBD8']]
    '''
        
    # drop out 'not fair' features and replace NaN with 0
    dataframe = dataCleansing(dataframe)

    # extract the input X from dataframe (matrix with <ncolumns> dimensions)
    ncolumns = dataframe.shape[1]    
    X = dataframe.values[:,0:ncolumns-1] #.astype(float)   
    Y = dataframe.values[:,ncolumns-1]    
    
    #TODO: this workaround is based in the same RAND_SEED used to split the same dataset used to trainning. Would be
    #better to split one time, save the train/validation data in two csv files and use them.
    if inputHasTrainedData:
        X_train, X_validation, Y_train, Y_validation = cross_validation.train_test_split(X, Y, test_size=VALIDATION_SIZE, random_state=RAND_SEED)

        X = X_validation
        X_objectIDs = X_validation[:,0:1]    
    
    
    # load trained model
    trainedModel = joblib.load(modelFileName)
    
    # apply the model to the input X and get all predicions
    prediction = predict(trainedModel, X).astype(int)
    
    # transform the predicion result from [1 0 1 1 ...] to [[1] [0] [1] [1] ...] 
    # in order to concatenate the predicion with the X_objectIDs
    prediction = prediction.reshape((len(prediction), 1))

    # merge the student ID with dropout predicion result
    id_and_prediction = numpy.concatenate((X_objectIDs, prediction), axis=1)
    
    # transform the array into a DataFrame
    resultDataframe = pandas.DataFrame(id_and_prediction, columns=['hash_cod_matricula', 'dropout-predicion'])
    
    # save the result to a CSV file
    resultDataframe.to_csv(outputFileName, sep=';')
    
    return resultDataframe

def predict(trainedModel, X):
    rescaledX = rescaleData(X)
    predictions = trainedModel.predict(rescaledX)
    
    return predictions

def printModelAccuracy(Y_validation, predictions):
    print '\n=== Model Accuracy ==='

    print '\naccuracy_score:'
    print(accuracy_score(Y_validation, predictions))
    
    print '\nconfusion_matrix:'
    print '=> By definition a confusion matrix C is such that C_{i, j} is equal to the number of observations known to be in group i but predicted to be in group j.'
    print(confusion_matrix(Y_validation, predictions))
    
    print '\nclassification_report:'
    print '=> http://machinelearningmastery.com/classification-accuracy-is-not-enough-more-performance-measures-you-can-use/'
    print(classification_report(Y_validation, predictions))
    
def checkPredictionAccuracy(predictionsDataframe, inputFileName, inputHasTrainedData):
    # extract the Y_validation from CSV file (assuming it's the last column)
    dataframe = loadDataframe(inputFileName)    
    
    #ncolumns = dataframe.shape[1]
    #Y_validation = dataframe.values[:,ncolumns-1].astype(int) 
    
    
    ncolumns = dataframe.shape[1]    
    X = dataframe.values[:,0:ncolumns-1] #.astype(float)   
    Y = dataframe.values[:,ncolumns-1].astype(int) 
    
    Y_validation = Y
    
    #TODO: this workaround is based in the same RAND_SEED used to split the same dataset used to trainning. Would be
    #better to split one time, save the train/validation data in two csv files and use them.
    if inputHasTrainedData:
        X_train, X_validation, Y_train, Y_validation = cross_validation.train_test_split(X, Y, test_size=VALIDATION_SIZE, random_state=RAND_SEED)    
        
    # extract the predictions from predictionsDataframe (assuming it's the last column)
    pncolumns = predictionsDataframe.shape[1]
    predictions = predictionsDataframe.values[:,pncolumns-1].astype(int)

    # print accuracy reports
    printModelAccuracy(Y_validation, predictions)    
        
def trainStudentDropoutPrediction(inputFilePath, outputFileNameForModel):
    print 
    print '####################################################################'
    print '######### TRAINING ML Model for Student Dropout Prediction #########'
    print '####################################################################'
    print 
    
    # Load dataset
    dataframe = loadDataframe(inputFilePath)
    
    # drop out 'not fair' features
    dataframe = dataCleansing(dataframe)
            
    #Split-out train/validation dataset
    X_train, X_validation, Y_train, Y_validation = splitoutValidationDataset(dataframe)    

    # train an Logistic Regression model and save it to outputFileNameForModel
    trainedModel = trainAndSaveLRModel(X_train, Y_train, outputFileNameForModel)
    
    #debug only
    #trainedModel = joblib.load(outputFileNameForModel)
    
    
    #test the model accuracy with the test dataset X_validation
    predictions = predict(trainedModel, X_validation)
    printModelAccuracy(Y_validation, predictions)
