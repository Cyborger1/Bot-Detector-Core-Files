import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import datetime as dt
import numpy as np
import time
from joblib import dump, load
import Config

from sklearn.preprocessing import RobustScaler, Normalizer
from sklearn.decomposition import PCA
# custom
import SQL

def logging(f):
    def wrapper(df, *args, **kwargs):
        start = dt.datetime.now()
        result = f(df, *args, **kwargs)
        end = dt.datetime.now()
        try:
            Config.debug(f'{f.__name__} took: {end - start} shape= {result.shape}')
        except:
            Config.debug(f'{f.__name__} took: {end - start}')
        return result
    return wrapper

def get_highscores(ofinterest=True, start=0, amount=100_000):
    if ofinterest:
        data = SQL.get_hiscores_of_interst()
    else:
        data = SQL.get_highscores_data(start, amount)
    df_hiscore = pd.DataFrame(data)

    print(f'hiscore: {df_hiscore.shape}')
    return df_hiscore

def get_players(players=None, with_id=False, ofinterest=True, ids=None):
    # someday i need to rethink this
    if players is None:
        if ofinterest:
            data = SQL.get_players_of_interest()
        else:
            data = SQL.get_player_names(ids)
        players = pd.DataFrame(data)

    df_players = players
    df_players.set_index('name', inplace=True)

    if with_id:
        df_players.drop(columns=['created_at','updated_at'], inplace=True)
    else:
        df_players.drop(columns=['created_at','updated_at','id'], inplace=True)

    df_players['label_id'] = df_players['label_id'].replace(22, 5)

    print(f'players: {df_players.shape}')
    return df_players

def get_labels():
    data = SQL.get_player_labels()
    labels = pd.DataFrame(data)
    df_labels = labels.set_index('id')

    print(f'labels: {df_labels.shape}')
    return df_labels

@logging
def start_pipeline(df):
    return df.copy()

@logging
def start_pipeline(df):
    return df.copy()

@logging
def clean_dataset(df, skills_list, minigames_list):
    # sort by timestamp, drop duplicates keep last
    df = df.sort_values('timestamp').drop_duplicates('Player_id',keep='last')

    # drop unrelevant columns
    df.drop(columns=['id','timestamp','ts_date','Player_id'], inplace=True)

    # set unique index
    df.set_index(['name'], inplace=True)

    # total is sum of all skills
    df[skills_list] = df[skills_list].replace(-1, 0)
    df['total'] = df[skills_list].sum(axis=1)
    

    # replace -1 values
    df[skills_list] = df[skills_list].replace(0, 1)
    df[minigames_list] = df[minigames_list].replace(-1, 0)

    df['boss_total'] = df[minigames_list].sum(axis=1)

    return df

def zalcano_feature(df):
    zalcano_mining      = df['zalcano'] * 13_500    / 15
    zalcano_smithing    = df['zalcano'] * 3_000     / 15
    zalcano_rc          = df['zalcano'] * 1_500     / 15
    lvl70skill          = 737_627

    df['zalcano_feature'] = (
        zalcano_mining      / (df['mining']     - lvl70skill) + 
        zalcano_smithing    / (df['smithing']   - lvl70skill) + 
        zalcano_rc          / (df['runecraft'])
    )
        
    req = ['agility','construction','farming','herblore','hunter','smithing','woodcutting']

    df['zalcano_flag_feature']              = np.where(df[req].min(axis=1) > lvl70skill, 1, 0) 
    df['zalcano_req_overshoot_feature']     = df[req].mean(axis=1) - lvl70skill
    # df['zalcano_req_overshoot_feature']     = np.where(df['zalcano_req_overshoot_feature'] < 0, 0, df['zalcano_req_overshoot_feature'])
    return df

def wintertodt_feature(df):
    wintertodt_fm = df['wintertodt']*30_000
    lvl50skill = 101_333

    df['wintertodt_feature']        = wintertodt_fm/(df['firemaking'] - lvl50skill)

    df['wintertodt_lag_feature']    = np.where(df['wintertodt'] > 670, 1, 0)
    return df

def botname(df):
    L = '[A-Za-z]'
    C = '[_-]'
    S = '[ ]'
    N = '[0-9]'
    name_transform = [
                      (L, 'L'), 
                      (C, 'C'), 
                      (S, 'S'), 
                      (N, 'N')]
    df['botname'] = df.index
    for token_regex, token in name_transform:
        df['botname'] = df['botname'].str.replace(token_regex, token)
    
    df['botname'] = df['botname'].astype("category").cat.add_categories([0])
    df['botname_feature'] = df['botname'].cat.codes
    return df

@logging
def f_features(df, skills_list, minigames_list):
    # save total column to variable
    total = df['total']
    boss_total =  df['boss_total']

    # for each skill, calculate ratio
    for skill in skills_list:
        df[f'{skill}/total'] = df[skill] / total

    for boss in minigames_list:
         df[f'{boss}/boss_total'] = df[boss] / boss_total


    # df = wintertodt_feature(df)
    # df = zalcano_feature(df)
    df = botname(df)
    # df['rangebot_feature'] = (df['ranged'] + df['hitpoints'])/total

    df['median_feature'] = df[skills_list].median(axis=1)
    df['mean_feature'] = df[skills_list].mean(axis=1)
    # df['std_feature'] = df[skills_list].std(axis=1)

    # df['bot_name_feature'] = botname(df)
    # replace infinities & nan
    df = df.replace([np.inf, -np.inf], 0) 
    df.fillna(0, inplace=True)

    return df

@logging
def filter_relevant_features(df, skills_list ,myfeatures=None):
    if myfeatures is not None:
        return df[myfeatures].copy()
        
    # all features
    features =  df.columns
    
    features = [f for f in features if '/total' in f or '/boss_total' in f or '_feature' in f]
    return df[features].copy()


@logging
def f_standardize(df, scaler=None, dummy=False):
    if scaler is None:
        print('new scaler')
        scaler = RobustScaler()
        scaler = scaler.fit(df)

        today = int(time.time())
        dump(value=scaler, filename=f'Predictions/models/scaler_{today}_100.joblib')
    
    if dummy: 
        return df

    X_scaled = scaler.transform(df) 
    return pd.DataFrame(X_scaled, columns=df.columns, index=df.index)

@logging
def f_normalize(df, transformer=None, dummy=False):
    if transformer is None:
        print('new normalizer')
        transformer = Normalizer()
        transformer = transformer.fit(df)

        today = int(time.time())
        dump(value=transformer, filename=f'Predictions/models/normalizer_{today}_100.joblib')

    if dummy: 
        return df

    X_normalized = transformer.transform(df)
    return pd.DataFrame(X_normalized, columns=df.columns, index=df.index)


def f_pca(df, n_components='mle', pca=None):
    n_components = int(n_components) if n_components != 'mle' else n_components
    if pca is None:
        pca = PCA(n_components=n_components, random_state=7) 
        pca = pca.fit(df)

        today = int(time.time())
        n_components = pca.n_components_
        dump(value=pca, filename=f'Predictions/models/pca_{today}_{n_components}.joblib')
        
    # Apply dimensionality reduction to X.
    X_principal = pca.transform(df)

    # rename columns and put in dataframe
    columns = [f'P{c}' for c in range(n_components)]
    df = pd.DataFrame(X_principal, columns=columns, index=df.index) 
    df.dropna(inplace=True)
    return df, pca

def best_file_path(startwith, dir='Predictions/models'):
    files = []
    for f in os.listdir(dir):
        if f.endswith(".joblib") and f.startswith(startwith):
            # accuracy is in filename, so we have to parse it
            model_file = f.replace('.joblib','')
            model_file = model_file.split(sep='_')
            # save to dict
            d ={
                'path': f'{dir}/{f}',
                'model': model_file[0],
                'date': model_file[1],
                'accuracy': model_file[2]
            }
            # add dict to array
            files.append(d)
    # array of dict can be used for pandas dataframe
    df_files = pd.DataFrame(files)
    df_files.sort_values(by=['date'], ascending=False, inplace=True)
    model_path = df_files['path'].iloc[0]
    accuracy = df_files['accuracy'].iloc[0]
    return model_path, accuracy