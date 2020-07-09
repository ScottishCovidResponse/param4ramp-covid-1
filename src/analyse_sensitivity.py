"""Parameter Sensitivity Analysis for Contact Tracing Model
Sample pairs of (parameters, output summary) must be generated by param_samples.py in advance.

Usage:
  analyse_sensitivity.py <INPUT_DIR> <OUTPUT_DIR> [--seed=<seed>]
  analyse_sensitivity.py (-h | --help)
  analyse_sensitivity.py --version

Options:
  -h --help                       Show this screen.
  --version                       Show version.
  --seed=<seed>                   Random seed [default: 1234].
  
"""

import numpy as np
import pandas as pd
import os
from docopt import docopt
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.model_selection import GridSearchCV
from sklearn.model_selection import train_test_split
from six.moves import cPickle as pickle
import shap
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt

if __name__ == '__main__':
    args = docopt(__doc__, version='0.0.1')
    
    def _getopt(key, default):
        return args[key] if key in args and args[key] is not None else default

    indir = _getopt('<INPUT_DIR>', None)
    outdir = _getopt('<OUTPUT_DIR>', None)
    seed = int(_getopt('--seed', 1234))

    X = pd.read_csv('{}/input_parameter_samples.csv'.format(indir), index_col=0)
    Y = pd.read_csv('{}/output_loss_samples.csv'.format(indir), index_col=0)
    X = X.set_index(X.columns[0])
    Y = Y.set_index(Y.columns[0])
    
    try:
        os.mkdir(outdir)
    except:
        pass

    imp = []
    for metric in Y.columns:
        X_train, X_test, y_train, y_test = train_test_split(X, Y[metric], test_size=0.5, random_state=seed)
        n_train = X_train.shape[0]
        ms_list = np.unique(np.round(np.logspace(np.log10(2.0), np.log10(np.min([1000, n_train / 2])), 10)).astype(int))
        
        model_cv = GridSearchCV(
            estimator=ExtraTreesRegressor(
                n_estimators=100,
                criterion='mse',
                max_depth=None,
                bootstrap=True,
                oob_score=False,
                random_state=seed),
            param_grid={
                'min_samples_split': ms_list,
                'max_features': [int(1), 0.33, 1.0]
                },
            scoring='neg_mean_squared_error').fit(X_train, y_train)
            
        # By using best complexity, fit a final model with larger number of trees
        model = ExtraTreesRegressor(
            n_estimators=1000,
            criterion='mse',
            max_depth=None,
            bootstrap=True,
            min_samples_split=model_cv.best_params_['min_samples_split'],
            max_features=model_cv.best_params_['max_features'],
            oob_score=False,
            random_state=seed).fit(X_train, y_train)
        
        fimp = model.feature_importances_
        fimp /= fimp.sum()
        imp.append(fimp.reshape(-1, 1))
    
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_test)
        
        with open('{}/{}.model'.format(outdir, metric), 'wb') as fout:
            pickle.dump(model, fout)
        
        with PdfPages('{}/{}.pdf'.format(outdir, metric)) as pdf:
            plt.figure(figsize=(6, 6))
            plt.scatter(model.predict(X_test), y_test)
            plt.subplots_adjust(left=0.18, bottom=0.12, right=0.98, top=0.92)
            plt.title('{}\nForecast by Meta-Model vs Actual Outcome by Simulator'.format(metric))
            plt.xlabel('Forecast')
            plt.ylabel('Actual')
            pdf.savefig()
            plt.close()

            plt.figure(figsize=(12, 6))
            shap.summary_plot(shap_values, X_test, show=False, plot_size=(12, 6))
            plt.subplots_adjust(left=0.28, bottom=0.12, right=0.98, top=0.92)
            plt.title('Datapoint-specific Sensitivities to {}'.format(metric))
            pdf.savefig()
            plt.close()

            for xcol in X.columns:
                plt.figure(figsize=(6, 6))
                shap.dependence_plot(xcol, shap_values, X_test, show=False)
                plt.subplots_adjust(left=0.18, bottom=0.12, right=0.98, top=0.92)
                plt.title('How Interaction with {} Affects {}'.format(xcol, metric))
                pdf.savefig()
                plt.close()
        
    imp = pd.DataFrame(data=np.hstack(tuple(imp)), index=X.columns, columns=Y.columns)
    imp.to_csv('{}/relative_importance.csv'.format(outdir))
    
